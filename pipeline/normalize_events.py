"""Roll raw/ucr_events/*.json into Supabase `events` table.

Maps Localist event payloads to the `events` schema (snake_case columns,
matching CampusEvent fields). Idempotent: upserts by `id`, so re-running
overwrites stale rows.

Future structured sources (highlanderlink.ucr.edu, etc.) should plug in here
too — add another collector, map to the same row shape, append.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from config import RAW_DIR, ensure_dirs
from db import upsert_batched

log = logging.getLogger("pipeline.normalize_events")

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


def _start_end(raw: dict[str, Any]) -> tuple[str, str | None]:
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

    ticket_url = raw.get("ticket_url")

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
        "source_url": raw.get("localist_url") or raw.get("url"),
        "image_url": raw.get("photo_url"),
        "is_free": bool(raw.get("free", True)),
        "rsvp_required": bool(ticket_url),
        "rsvp_url": ticket_url or None,
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

    # Dedupe by id (last-write-wins).
    by_id: dict[str, dict[str, Any]] = {r["id"]: r for r in rows}
    deduped = list(by_id.values())

    written = upsert_batched("events", deduped)
    log.info("Wrote %d events to Supabase", written)


if __name__ == "__main__":
    main()
