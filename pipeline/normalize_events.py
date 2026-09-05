"""Roll raw event JSON from structured campus sources into Supabase `events`.

Currently handles two sources, both mapped to the same `events` row shape
(snake_case columns matching CampusEvent fields):

  - Localist (events.ucr.edu)         -> data/raw/ucr_events/*.json
  - CampusLabs Engage (HighlanderLink) -> data/raw/highlander_link/*.json

Idempotent: upserts by `id`, so re-running overwrites stale rows. Add new
structured sources by writing a `_to_event_row_<source>` mapper plus a
collector pass in `main()`.
"""
from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from classify import classify_content_kind, detect_free_food
from config import RAW_DIR, ensure_dirs
from db import delete_events_missing_from_ids, get_deleted_event_ids, upsert_batched
from discord_notify import notify_free_food_events
from event_identity import dedupe_event_rows, suppress_tombstoned_event_groups
from url_utils import normalize_http_url as _normalize_url

log = logging.getLogger("pipeline.normalize_events")

UCR_EVENTS_RAW = RAW_DIR / "ucr_events"
HIGHLANDER_LINK_RAW = RAW_DIR / "highlander_link"
STRUCTURED_EVENT_ID_PREFIXES = ["ucr_events_", "highlander_link_"]

# --------------------------------------------------------------------------
# Category inference
#
# Structured sources tag their own events, and those tags beat anything we can
# guess from prose. Resolution runs in three explicit tiers:
#
#   1. Source taxonomy — Localist `event_types`/`event_athletics` and Engage
#      `theme`/`categoryNames`, matched as whole labels against the tables
#      below.
#   2. Keyword scoring — whole-word hits in the title, description and any
#      leftover source labels, weighted by field and tie-broken by an explicit
#      priority order.
#   3. `community` — the catch-all when nothing matched.
#
# Tier 1 is why "Power Yoga" (Localist type "Recreation") is sports: it never
# reaches the keyword pass, where the substring "class" in its blurb used to
# decide the category purely because "academic" sat first in the keyword list.
# --------------------------------------------------------------------------

# Localist `event_types`, most specific first — the first label present on the
# event decides. Order matters for the multi-typed events: "Recreation, Social"
# is a rec-center session, and "Academic Calendar, Commencement" is the
# ceremony rather than a registration deadline. Matching is on the whole label,
# so "Academic Calendar" never reads as bare "Academic".
_LOCALIST_TYPE_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("theatre & plays", "arts"),
    ("film & screenings", "arts"),
    ("exhibitions", "arts"),
    ("arts", "arts"),
    ("athletics", "sports"),
    ("recreation", "sports"),
    ("commencement", "community"),
    ("fundraisers", "community"),
    ("career", "career"),
    ("conferences", "career"),
    ("seminars", "academic"),
    ("lectures & presentations", "academic"),
    ("academic calendar", "academic"),
    ("academic", "academic"),
    ("social", "social"),
)

# Deliberately absent above: "Workshops" and "Meetings & Training" hang off
# everything from PhD defenses to HR compliance training, so they carry no
# category on their own and fall through to the keyword pass as weak hints.

# Engage 'theme' is a single coarse bucket per event; map it onto our category
# vocabulary. Keyed lowercase — Engage spells them CamelCase.
_HLINK_THEME_TO_CATEGORY = {
    "athletics": "sports",
    "cultural": "arts",
    "social": "social",
    "spirituality": "community",
    "communityservice": "community",
    "fundraising": "community",
    "thoughtfullearning": "academic",
}

# Engage `categoryNames` are per-org free text and an event carries several
# ("Free Food", "Just Show Up!", "Concert"), so only labels that name a
# category outright are mapped, and only after `theme` declines.
_HLINK_CATEGORY_NAME_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("concert", "arts"),
    ("performance", "arts"),
    ("exhibit", "arts"),
    ("dance", "arts"),
    ("cultural", "arts"),
    ("competition", "sports"),
    ("recreational", "sports"),
    ("educational", "academic"),
    ("community service", "community"),
    ("late night", "social"),
    ("gaming", "social"),
    ("social", "social"),
)

# Keyword fallback for events whose source tags are missing or non-committal.
# Matched whole-word (plus an optional plural), so "class" no longer fires on
# "Classical Pilates". A couple of obvious-looking words are absent because the
# bare form is not category-bearing on this campus: "performance" caught HR
# trainings about employee performance, and "service" caught "military service"
# (real community-service posts still match on "community").
_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "academic": ("lecture", "seminar", "colloquium", "symposium", "research", "thesis", "defense", "class"),
    "career": ("career", "internship", "workshop", "networking", "resume", "interview", "hiring", "recruit"),
    "sports": ("athletic", "basketball", "soccer", "baseball", "volleyball", "tennis", "football", "intramural"),
    "arts": ("concert", "recital", "exhibit", "exhibition", "gallery", "theater", "theatre", "dance performance", "film", "screening"),
    "social": ("mixer", "social", "party", "greek", "fraternity", "sorority", "kickback"),
    "club": ("club", "organization", "rso", "general meeting", "gbm"),
    "community": ("community", "volunteer", "outreach", "donate"),
}

# Tie-break for the keyword pass, most-unambiguous vocabulary first: "soccer"
# and "recital" name a category outright, while "class", "social" and
# "workshop" turn up in half of what campus posts. `community` stays last —
# it doubles as the default when nothing matches at all.
_CATEGORY_PRIORITY: tuple[str, ...] = (
    "sports",
    "arts",
    "career",
    "club",
    "academic",
    "social",
    "community",
)
_CATEGORY_RANK: dict[str, int] = {c: i for i, c in enumerate(_CATEGORY_PRIORITY)}
_UNRANKED = len(_CATEGORY_PRIORITY)

# A title hit is worth more than a hit buried in a long blurb; leftover source
# labels ("Workshops", "Health & Wellness") sit in between.
_TITLE_WEIGHT = 3
_SOURCE_TERM_WEIGHT = 2
_DESCRIPTION_WEIGHT = 1


def _keyword_pattern(keywords: tuple[str, ...]) -> re.Pattern[str]:
    # Longest alternative first so "exhibition" is not swallowed by "exhibit",
    # and the capture group reports the base keyword rather than the inflected
    # form, so "class" and "classes" count once.
    alternatives = "|".join(re.escape(kw) for kw in sorted(keywords, key=len, reverse=True))
    return re.compile(rf"\b({alternatives})(?:e?s)?\b")


_CATEGORY_PATTERNS: dict[str, re.Pattern[str]] = {
    category: _keyword_pattern(keywords) for category, keywords in _CATEGORY_KEYWORDS.items()
}

_HTML_TAG = re.compile(r"<[^>]+>")

_WHITESPACE = re.compile(r"\s+")


def _strip_html(s: str | None) -> str:
    if not s:
        return ""
    return _WHITESPACE.sub(" ", html.unescape(_HTML_TAG.sub(" ", s))).strip()


def _filter_names(raw: dict[str, Any], key: str) -> list[str]:
    filters = raw.get("filters") or {}
    bucket = filters.get(key) or []
    out: list[str] = []
    for item in bucket:
        if isinstance(item, dict):
            name = item.get("name")
            if name:
                out.append(str(name))
        elif isinstance(item, str):
            out.append(item)
    return out


def _match_source_category(
    labels: Iterable[str],
    table: tuple[tuple[str, str], ...],
) -> str | None:
    """First entry in `table` whose label the source put on this event.

    Whole-label equality, not substring: a source that says "Academic Calendar"
    has not said "Academic".
    """
    present = {label.strip().lower() for label in labels if isinstance(label, str) and label.strip()}
    for label, category in table:
        if label in present:
            return category
    return None


def _infer_category_from_text(
    title: str,
    description: str,
    source_terms: Iterable[str] = (),
) -> str:
    """Score keyword hits across the weighted fields; ties go to the priority order.

    Each distinct keyword scores once, at the weight of the strongest field it
    appeared in, so breadth of vocabulary wins over one word repeated through a
    long blurb.
    """
    fields = (
        (title.lower(), _TITLE_WEIGHT),
        (" ".join(t for t in source_terms if isinstance(t, str)).lower(), _SOURCE_TERM_WEIGHT),
        (description.lower(), _DESCRIPTION_WEIGHT),
    )

    scores: dict[str, int] = {}
    for category, pattern in _CATEGORY_PATTERNS.items():
        best: dict[str, int] = {}
        for text, weight in fields:
            if not text:
                continue
            for keyword in pattern.findall(text):
                if weight > best.get(keyword, 0):
                    best[keyword] = weight
        if best:
            scores[category] = sum(best.values())

    if not scores:
        return "community"
    return max(scores, key=lambda c: (scores[c], -_CATEGORY_RANK.get(c, _UNRANKED)))


def _infer_localist_category(raw: dict[str, Any], title: str, description: str) -> str:
    # An `event_athletics` tag (Soccer, Basketball, …) only lands on real games.
    if _filter_names(raw, "event_athletics"):
        return "sports"
    types = _filter_names(raw, "event_types")
    mapped = _match_source_category(types, _LOCALIST_TYPE_CATEGORIES)
    if mapped:
        return mapped
    # Types were missing or non-committal ("Workshops"); let them and the
    # free-text topics weigh in as keywords alongside the title and body.
    return _infer_category_from_text(title, description, [*types, *_filter_names(raw, "event_topic")])


def _infer_hlink_category(
    theme: Any,
    category_names: list[str],
    title: str,
    description: str,
) -> str:
    if isinstance(theme, str):
        mapped = _HLINK_THEME_TO_CATEGORY.get(theme.strip().lower())
        if mapped:
            return mapped
    mapped = _match_source_category(category_names, _HLINK_CATEGORY_NAME_CATEGORIES)
    if mapped:
        return mapped
    return _infer_category_from_text(title, description, category_names)


def _build_location(raw: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("location_name", "room_number", "address"):
        val = raw.get(key)
        if val and isinstance(val, str) and val.strip():
            parts.append(val.strip())
    deduped: list[str] = []
    for p in parts:
        if not deduped or deduped[-1].lower() != p.lower():
            deduped.append(p)
    return ", ".join(deduped) or "UC Riverside"


def _build_host(raw: dict[str, Any]) -> str:
    custom = raw.get("custom_fields") or {}
    if isinstance(custom, dict):
        for key in ("department", "host", "organizer", "sponsor"):
            val = custom.get(key)
            if val and isinstance(val, str) and val.strip():
                return val.strip()
    # No real organizer field: Localist events fall back to their event_type
    # bucket ("Recreation", "Arts", "Seminars", …). Bare, these read as a host
    # AND collide with our category chip labels ("Arts", "Academic", "Social"),
    # so prefix with "UCR" to mark them as a campus area, not an organization.
    types = _filter_names(raw, "event_types")
    if types:
        return f"UCR {types[0]}"
    return "UC Riverside"


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def _extract_instances(instances: Any) -> list[dict[str, Any]]:
    if not isinstance(instances, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in instances:
        if not isinstance(entry, dict):
            continue
        inner = entry.get("event_instance") or entry
        if not isinstance(inner, dict):
            continue
        if inner.get("start"):
            out.append(inner)
    return out


def _upcoming_instances(
    instances: Any,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    parsed: list[tuple[datetime, dict[str, Any]]] = []
    for inner in _extract_instances(instances):
        ts = _parse_iso(inner.get("end") or inner.get("start"))
        if ts is None:
            continue
        parsed.append((ts, inner))
    if not parsed:
        return []
    parsed.sort(key=lambda x: x[0])
    cutoff = now or datetime.now(timezone.utc)
    return [inner for ts, inner in parsed if ts >= cutoff]


def _latest_instance(instances: Any) -> dict[str, Any] | None:
    parsed: list[tuple[datetime, dict[str, Any]]] = []
    for inner in _extract_instances(instances):
        ts = _parse_iso(inner.get("end") or inner.get("start"))
        if ts is None:
            continue
        parsed.append((ts, inner))
    if not parsed:
        return None
    parsed.sort(key=lambda x: x[0])
    return parsed[-1][1]


def _is_recurring_localist_event(raw: dict[str, Any]) -> bool:
    recurring = raw.get("recurring")
    if isinstance(recurring, bool):
        return recurring
    if isinstance(recurring, str):
        return recurring.strip().lower() in {"1", "true", "yes", "y"}
    return len(_extract_instances(raw.get("event_instances"))) > 1


def _start_end(raw: dict[str, Any]) -> tuple[str, str | None]:
    chosen_instances = _upcoming_instances(raw.get("event_instances"))
    chosen = chosen_instances[0] if chosen_instances else None
    if chosen is not None:
        start = chosen.get("start") or raw.get("first_date")
        end = chosen.get("end") or raw.get("last_date")
        if start:
            return start, (end if end and end != start else None)
    start = raw.get("first_date") or raw.get("start") or ""
    end = raw.get("last_date") or raw.get("end")
    return start, (end if end and end != start else None)


def _instance_suffix(instance: dict[str, Any]) -> str:
    instance_id = instance.get("id")
    if instance_id is not None:
        return str(instance_id)
    start = str(instance.get("start") or "").strip()
    return re.sub(r"[^0-9A-Za-z]+", "", start) or "instance"


def _localist_row_id(localist_id: Any, instance: dict[str, Any] | None = None) -> str:
    base = f"ucr_events_{localist_id}"
    if instance is None:
        return base
    return f"{base}_{_instance_suffix(instance)}"


def _to_event_row(
    raw: dict[str, Any],
    scraped_at: str,
    instance: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    lid = raw.get("id")
    if lid is None:
        return None

    title = (raw.get("title") or "").strip()
    if not title:
        return None

    description = (
        raw.get("description_text")
        or _strip_html(raw.get("description"))
        or ""
    ).strip()

    if instance is not None:
        starts_at = instance.get("start") or raw.get("first_date") or raw.get("start") or ""
        end = instance.get("end") or None
        ends_at = end if end and end != starts_at else None
    else:
        starts_at, ends_at = _start_end(raw)
    if not starts_at:
        return None

    blob = f"{title}\n{description}"
    category = _infer_localist_category(raw, title, description)

    audiences = _filter_names(raw, "event_audience")
    tags = sorted(
        set(
            _filter_names(raw, "event_types")
            + _filter_names(raw, "event_topic")
            + audiences
        )
    )
    hashtag = raw.get("hashtag")
    if hashtag and isinstance(hashtag, str):
        tags.append(f"#{hashtag.lstrip('#')}")

    ticket_url = _normalize_url(raw.get("ticket_url"))
    row_instance = instance if instance is not None and _is_recurring_localist_event(raw) else None

    return {
        "id": _localist_row_id(lid, row_instance),
        "title": title[:200],
        "description": description,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "location": _build_location(raw),
        "host": _build_host(raw),
        "category": category,
        "content_kind": classify_content_kind(
            "localist",
            title=title,
            description=description,
            tags=tags,
            audiences=audiences,
        ),
        "tags": tags,
        "source": "campus_website",
        "source_url": _normalize_url(raw.get("localist_url") or raw.get("url")),
        "image_url": _normalize_url(raw.get("photo_url")),
        "is_free": bool(raw.get("free", True)),
        "has_free_food": detect_free_food(blob, *tags),
        "rsvp_required": bool(ticket_url),
        "rsvp_url": ticket_url or None,
        "scraped_at": scraped_at,
    }


def _to_event_rows(
    raw: dict[str, Any],
    scraped_at: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    if _is_recurring_localist_event(raw):
        instances = _upcoming_instances(raw.get("event_instances"), now=now)
        if not instances:
            last_instance = _latest_instance(raw.get("event_instances"))
            if last_instance is not None:
                instances = [last_instance]
            else:
                fallback_row = _to_event_row(raw, scraped_at)
                return [fallback_row] if fallback_row is not None else []
        rows = [
            row
            for instance in instances
            if (row := _to_event_row(raw, scraped_at, instance=instance)) is not None
        ]
        return rows
    single_instance = _extract_instances(raw.get("event_instances"))
    row = _to_event_row(raw, scraped_at, instance=single_instance[0] if single_instance else None)
    return [row] if row is not None else []


_HLINK_IMAGE_BASE = "https://se-images.campuslabs.com/clink/images/"
_HLINK_EVENT_URL = "https://highlanderlink.ucr.edu/event/{id}"


def _to_event_row_hlink(raw: dict[str, Any], scraped_at: str) -> dict[str, Any] | None:
    eid = raw.get("id")
    if eid is None:
        return None

    title = (raw.get("name") or "").strip()
    if not title:
        return None

    description = _strip_html(raw.get("description"))

    starts_at = raw.get("startsOn")
    ends_at = raw.get("endsOn")
    if not starts_at:
        return None
    if ends_at == starts_at:
        ends_at = None

    benefits = raw.get("benefitNames") or []
    category_names = [c for c in (raw.get("categoryNames") or []) if isinstance(c, str)]
    category = _infer_hlink_category(raw.get("theme"), category_names, title, description)

    has_free_food = (
        isinstance(benefits, list)
        and any(isinstance(b, str) and b.lower() == "free food" for b in benefits)
    ) or detect_free_food(title, description)

    tags = sorted(
        {
            *category_names,
            *(t for t in benefits if isinstance(t, str)),
            *([raw["theme"]] if isinstance(raw.get("theme"), str) else []),
        }
    )

    image_path = raw.get("imagePath")
    image_url = _normalize_url(f"{_HLINK_IMAGE_BASE}{image_path}" if image_path else None)

    host = (raw.get("organizationName") or "").strip() or "UC Riverside"
    location = (raw.get("location") or "").strip() or "UC Riverside"

    return {
        "id": f"highlander_link_{eid}",
        "title": title[:200],
        "description": description,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "location": location,
        "host": host,
        "category": category,
        "content_kind": classify_content_kind(
            "highlander_link",
            title=title,
            description=description,
            tags=tags,
        ),
        "tags": tags,
        "source": "campus_website",
        "source_url": _normalize_url(_HLINK_EVENT_URL.format(id=eid)),
        "image_url": image_url,
        "is_free": True,
        "has_free_food": has_free_food,
        "rsvp_required": False,
        "rsvp_url": None,
        "scraped_at": scraped_at,
    }


def _collect_raw(
    source_dir: Path,
    require_complete: bool = False,
) -> Iterable[dict[str, Any]]:
    if not source_dir.exists():
        if require_complete:
            raise ValueError(f"verified source directory is missing: {source_dir}")
        return
    paths = list(source_dir.glob("*.json"))
    if require_complete and not paths:
        raise ValueError(f"verified source directory is empty: {source_dir}")
    for path in paths:
        try:
            with path.open(encoding="utf-8") as f:
                yield json.load(f)
        except json.JSONDecodeError as e:
            if require_complete:
                raise ValueError(f"verified source contains malformed JSON: {path}") from e
            log.warning("skipping malformed file: %s", path)


def _filter_deleted_events(
    rows: list[dict[str, Any]],
    deleted_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not rows:
        return []

    if deleted_ids is None:
        deleted_ids = get_deleted_event_ids()
    if deleted_ids:
        log.info(
            "Found %d admin-deleted events. Excluding from structured importer run.",
            len(deleted_ids),
        )
        rows = suppress_tombstoned_event_groups(rows, deleted_ids)
    return rows


def _locked_event_ids() -> set[str]:
    try:
        from db import client

        db_client = client()
        locked_res = db_client.table("events").select("id").eq("is_locked", True).execute()
        return {row["id"] for row in getattr(locked_res, "data", []) or []}
    except Exception as e:
        log.warning("Could not fetch locked events for exclusion: %s. Proceeding with all events.", e)
        return set()


def main(reconcile_prefixes: Iterable[str] = ()) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ensure_dirs()
    scraped_at = datetime.now(timezone.utc).isoformat()
    verified_prefixes = set(reconcile_prefixes)

    rows: list[dict[str, Any]] = []
    for raw in _collect_raw(
        UCR_EVENTS_RAW,
        require_complete="ucr_events_" in verified_prefixes,
    ):
        rows.extend(_to_event_rows(raw, scraped_at))
    for raw in _collect_raw(
        HIGHLANDER_LINK_RAW,
        require_complete="highlander_link_" in verified_prefixes,
    ):
        row = _to_event_row_hlink(raw, scraped_at)
        if row is not None:
            rows.append(row)

    locked_ids = _locked_event_ids()
    if locked_ids:
        log.info("Found %d manually locked events in database. Excluding from scraper run.", len(locked_ids))
        rows = suppress_tombstoned_event_groups(rows, locked_ids)

    deduped = dedupe_event_rows(_filter_deleted_events(rows))

    deleted = 0
    for prefix in STRUCTURED_EVENT_ID_PREFIXES:
        if prefix not in verified_prefixes:
            continue
        keep_ids = sorted(r["id"] for r in deduped if r["id"].startswith(prefix))
        deleted += delete_events_missing_from_ids([prefix], keep_ids)
    if deleted:
        log.info("Deleted %d stale structured event rows from Supabase", deleted)

    written = upsert_batched("events", deduped)
    log.info("Wrote %d events to Supabase", written)
    notified = notify_free_food_events(deduped)
    if notified:
        log.info("Sent %d free food Discord notifications", notified)


if __name__ == "__main__":
    main()
