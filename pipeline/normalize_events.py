"""Roll raw/ucr_events/*.json into output/events.json in CampusEvent shape.

This is the structured-event counterpart to normalize.py (which handles IG
stories). Future structured sources (highlanderlink.ucr.edu, etc.) should
plug in here too — add another collector, map to CampusEvent, append.

The output schema mirrors the TypeScript CampusEvent interface in
src/types/event.ts. Keep them in sync.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from config import OUTPUT_DIR, RAW_DIR, ensure_dirs

log = logging.getLogger("pipeline.normalize_events")

EVENTS_OUTPUT_FILE = OUTPUT_DIR / "events.json"
UCR_EVENTS_RAW = RAW_DIR / "ucr_events"

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


def _strip_html(s: str | None) -> str:
    if not s:
        return ""
    return _WHITESPACE.sub(" ", _HTML_TAG.sub(" ", s)).strip()


def _filter_names(raw: dict[str, Any], key: str) -> list[str]:
    """Localist filters live under `filters.event_types`, `filters.event_topic`, etc.

    Each value is a list of {id, name} or similar. We just want the names.
    """
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
    type_names = " ".join(_filter_names(raw, "event_types")).lower()
    topic_names = " ".join(_filter_names(raw, "event_topic")).lower()
    haystack = " ".join([type_names, topic_names, blob.lower()])

    if _FREE_FOOD_PATTERNS.search(blob):
        return "free_food"

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
    # Deduplicate consecutive identical parts (e.g. when address == location_name)
    deduped: list[str] = []
    for p in parts:
        if not deduped or deduped[-1].lower() != p.lower():
            deduped.append(p)
    return ", ".join(deduped) or "UC Riverside"


def _build_host(raw: dict[str, Any]) -> str:
    # Localist doesn't have a clean "organizer" field on the basic event payload.
    # The closest signal is event_types (often department-shaped) or custom_fields.
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


def _start_end(raw: dict[str, Any]) -> tuple[str, str | None]:
    # Prefer the first instance's start/end if present (more accurate for recurring),
    # else fall back to top-level first_date / last_date.
    instances = raw.get("event_instances") or []
    if instances and isinstance(instances, list):
        first = instances[0]
        if isinstance(first, dict):
            inner = first.get("event_instance") or first
            start = inner.get("start") or raw.get("first_date")
            end = inner.get("end") or raw.get("last_date")
            if start:
                return start, (end if end and end != start else None)

    start = raw.get("first_date") or raw.get("start") or ""
    end = raw.get("last_date") or raw.get("end")
    return start, (end if end and end != start else None)


def _to_campus_event(raw: dict[str, Any], generated_at: str) -> dict[str, Any] | None:
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

    ticket_url = raw.get("ticket_url")

    return {
        "id": f"ucr_events_{lid}",
        "title": title[:200],
        "description": description,
        "startsAt": starts_at,
        "endsAt": ends_at,
        "location": _build_location(raw),
        "host": _build_host(raw),
        "category": category,
        "tags": tags,
        "source": "campus_website",
        "sourceUrl": raw.get("localist_url") or raw.get("url"),
        "imageUrl": raw.get("photo_url"),
        "isFree": bool(raw.get("free", True)),
        "rsvpRequired": bool(ticket_url),
        "rsvpUrl": ticket_url or None,
        "scrapedAt": generated_at,
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
    generated_at = datetime.now(timezone.utc).isoformat()

    events: list[dict[str, Any]] = []
    for raw in _collect_raw(UCR_EVENTS_RAW):
        ev = _to_campus_event(raw, generated_at)
        if ev is not None:
            events.append(ev)

    # Dedupe by id (last-write-wins) and sort chronologically.
    by_id: dict[str, dict[str, Any]] = {ev["id"]: ev for ev in events}
    sorted_events = sorted(by_id.values(), key=lambda e: e["startsAt"])

    payload = {
        "generatedAt": generated_at,
        "count": len(sorted_events),
        "events": sorted_events,
    }
    with EVENTS_OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log.info("Wrote %d events to %s", len(sorted_events), EVENTS_OUTPUT_FILE)


if __name__ == "__main__":
    main()
