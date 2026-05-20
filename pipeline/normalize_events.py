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
from urllib.parse import urlsplit

from config import RAW_DIR, ensure_dirs
from db import upsert_batched

log = logging.getLogger("pipeline.normalize_events")

UCR_EVENTS_RAW = RAW_DIR / "ucr_events"
HIGHLANDER_LINK_RAW = RAW_DIR / "highlander_link"

# Engage 'theme' is a single coarse bucket per event; map it onto our category
# vocabulary. categoryNames are more specific but free-text, so they're fed
# through the keyword fallback below.
_HLINK_THEME_TO_CATEGORY = {
    "Athletics": "sports",
    "Cultural": "arts",
    "Social": "social",
    "Spirituality": "community",
    "Fundraising": "community",
    "ThoughtfulLearning": "academic",
}

# Heuristic keyword sets for category inference. Localist's own event_types are
# the primary signal; these are fallbacks when types are missing/generic.
_CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("academic", ["lecture", "seminar", "colloquium", "symposium", "research", "thesis", "defense", "class"]),
    ("career",   ["career", "internship", "workshop", "networking", "resume", "interview", "hiring", "recruit"]),
    ("sports",   ["athletic", "basketball", "soccer", "baseball", "volleyball", "tennis", "football", "intramural"]),
    ("arts",     ["concert", "recital", "exhibit", "exhibition", "gallery", "theater", "theatre", "performance", "film", "screening"]),
    ("social",   ["mixer", "social", "party", "greek", "fraternity", "sorority", "kickback"]),
    ("club",     ["club", "organization", "rso", "general meeting", "gbm"]),
    ("community", ["community", "service", "volunteer", "outreach", "donate"]),
]

_FREE_FOOD_PATTERNS = re.compile(
    r"\b(free food|free pizza|pizza provided|free snacks|snacks provided|"
    r"refreshments|lunch provided|dinner provided|boba|free drinks)\b",
    re.IGNORECASE,
)

_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_URL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+\-.]*:", re.IGNORECASE)


def _strip_html(s: str | None) -> str:
    if not s:
        return ""
    return _WHITESPACE.sub(" ", html.unescape(_HTML_TAG.sub(" ", s))).strip()


def _normalize_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.startswith("//"):
        text = f"https:{text}"
    elif not _URL_SCHEME_RE.match(text):
        text = f"https://{text}"

    parsed = urlsplit(text)
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return text


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


def _infer_category(raw: dict[str, Any], blob: str) -> str:
    if _FREE_FOOD_PATTERNS.search(blob):
        return "free_food"
    type_names = " ".join(_filter_names(raw, "event_types")).lower()
    topic_names = " ".join(_filter_names(raw, "event_topic")).lower()
    haystack = " ".join([type_names, topic_names, blob.lower()])
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(kw in haystack for kw in keywords):
            return category
    return "community"


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
    types = _filter_names(raw, "event_types")
    if types:
        return types[0]
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


def _pick_instance(instances: Any) -> dict[str, Any] | None:
    """Next instance that hasn't ended yet, else the latest past one.

    Localist returns every upcoming occurrence of a recurring event in
    event_instances. Picking [0] always returned the earliest, even after
    it had finished — so a Friday-only series scraped Friday evening would
    keep reporting that morning's date until the next scrape.
    """
    if not isinstance(instances, list):
        return None
    parsed: list[tuple[datetime, dict[str, Any]]] = []
    for entry in instances:
        if not isinstance(entry, dict):
            continue
        inner = entry.get("event_instance") or entry
        if not isinstance(inner, dict):
            continue
        ts = _parse_iso(inner.get("end") or inner.get("start"))
        if ts is None:
            continue
        parsed.append((ts, inner))
    if not parsed:
        return None
    parsed.sort(key=lambda x: x[0])
    now = datetime.now(timezone.utc)
    for ts, inner in parsed:
        if ts >= now:
            return inner
    return parsed[-1][1]


def _start_end(raw: dict[str, Any]) -> tuple[str, str | None]:
    chosen = _pick_instance(raw.get("event_instances"))
    if chosen is not None:
        start = chosen.get("start") or raw.get("first_date")
        end = chosen.get("end") or raw.get("last_date")
        if start:
            return start, (end if end and end != start else None)
    start = raw.get("first_date") or raw.get("start") or ""
    end = raw.get("last_date") or raw.get("end")
    return start, (end if end and end != start else None)


def _to_event_row(raw: dict[str, Any], scraped_at: str) -> dict[str, Any] | None:
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

    starts_at, ends_at = _start_end(raw)
    if not starts_at:
        return None

    blob = f"{title}\n{description}"
    category = _infer_category(raw, blob)

    tags = sorted(
        set(
            _filter_names(raw, "event_types")
            + _filter_names(raw, "event_topic")
            + _filter_names(raw, "event_audience")
        )
    )
    hashtag = raw.get("hashtag")
    if hashtag and isinstance(hashtag, str):
        tags.append(f"#{hashtag.lstrip('#')}")

    ticket_url = _normalize_url(raw.get("ticket_url"))

    return {
        "id": f"ucr_events_{lid}",
        "title": title[:200],
        "description": description,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "location": _build_location(raw),
        "host": _build_host(raw),
        "category": category,
        "tags": tags,
        "source": "campus_website",
        "source_url": _normalize_url(raw.get("localist_url") or raw.get("url")),
        "image_url": _normalize_url(raw.get("photo_url")),
        "is_free": bool(raw.get("free", True)),
        "rsvp_required": bool(ticket_url),
        "rsvp_url": ticket_url or None,
        "scraped_at": scraped_at,
    }


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
    if isinstance(benefits, list) and any(
        isinstance(b, str) and b.lower() == "free food" for b in benefits
    ):
        category = "free_food"
    else:
        theme = raw.get("theme")
        category = _HLINK_THEME_TO_CATEGORY.get(theme) if isinstance(theme, str) else None
        if not category:
            # Fall back to keyword inference over categoryNames + title + body.
            cat_blob = " ".join(raw.get("categoryNames") or [])
            category = _infer_category({}, f"{cat_blob}\n{title}\n{description}")

    tags = sorted(
        {
            *(t for t in (raw.get("categoryNames") or []) if isinstance(t, str)),
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
        "tags": tags,
        "source": "campus_website",
        "source_url": _normalize_url(_HLINK_EVENT_URL.format(id=eid)),
        "image_url": image_url,
        "is_free": True,
        "rsvp_required": False,
        "rsvp_url": None,
        "scraped_at": scraped_at,
    }


def _collect_raw(source_dir: Path) -> Iterable[dict[str, Any]]:
    if not source_dir.exists():
        return
    for path in source_dir.glob("*.json"):
        try:
            with path.open(encoding="utf-8") as f:
                yield json.load(f)
        except json.JSONDecodeError:
            log.warning("skipping malformed file: %s", path)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ensure_dirs()
    scraped_at = datetime.now(timezone.utc).isoformat()

    rows: list[dict[str, Any]] = []
    for raw in _collect_raw(UCR_EVENTS_RAW):
        row = _to_event_row(raw, scraped_at)
        if row is not None:
            rows.append(row)
    for raw in _collect_raw(HIGHLANDER_LINK_RAW):
        row = _to_event_row_hlink(raw, scraped_at)
        if row is not None:
            rows.append(row)

    # Dedupe by id (last-write-wins).
    by_id: dict[str, dict[str, Any]] = {r["id"]: r for r in rows}
    deduped = list(by_id.values())

    written = upsert_batched("events", deduped)
    log.info("Wrote %d events to Supabase", written)


if __name__ == "__main__":
    main()
