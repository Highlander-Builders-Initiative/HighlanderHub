"""Fetch events from events.ucr.edu (Localist platform) via its JSON API.

Writes one JSON file per event to data/raw/ucr_events/<id>.json.

Unlike Instagram stories (which are immutable), Localist events are mutable —
descriptions get edited, locations change, etc. We always overwrite the raw
file so the on-disk copy reflects Localist's current state.

Localist API reference: https://developer.localist.com/doc/api
"""
from __future__ import annotations

import json
import logging
import random
import time
from typing import Any

import requests

from config import RAW_DIR, ensure_dirs

log = logging.getLogger("pipeline.ucr_events")

API_BASE = "https://events.ucr.edu/api/2/events"
LOOKAHEAD_DAYS = 90
PER_PAGE = 100  # Localist's documented max
SOURCE_DIR = RAW_DIR / "ucr_events"

# Stealthy UA: recent Chrome on Windows. Matches what a regular visitor sends.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://events.ucr.edu/",
        }
    )
    return s


def _fetch_page(s: requests.Session, page: int) -> dict[str, Any]:
    params = {"days": LOOKAHEAD_DAYS, "pp": PER_PAGE, "page": page}
    r = s.get(API_BASE, params=params, timeout=30)
    r.raise_for_status()
    # Localist's response sometimes lies about its charset; the body is UTF-8
    # but the headers can say ISO-8859-1, which mangles smart quotes/apostrophes.
    r.encoding = "utf-8"
    return r.json()


def _write_event(event: dict[str, Any]) -> bool:
    """Write event to raw/. Returns True if file is new, False if updated/unchanged."""
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    path = SOURCE_DIR / f"{event['id']}.json"
    is_new = not path.exists()
    with path.open("w", encoding="utf-8") as f:
        json.dump(event, f, indent=2, sort_keys=True, ensure_ascii=False)
    return is_new


def _prune_missing_events(seen_ids: set[str]) -> int:
    """Remove raw Localist files absent from a completed source scrape."""
    if not SOURCE_DIR.exists():
        return 0

    removed = 0
    for path in SOURCE_DIR.glob("*.json"):
        if path.stem in seen_ids:
            continue
        path.unlink()
        removed += 1
    return removed


def _events_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries = payload.get("events")
    if not isinstance(entries, list):
        raise ValueError("Localist response is missing an events list")

    events: list[dict[str, Any]] = []
    for entry in entries:
        event = entry.get("event") if isinstance(entry, dict) else None
        if not isinstance(event, dict):
            raise ValueError("Localist response contains a malformed event")
        if (
            event.get("id") is None
            or not isinstance(event.get("title"), str)
            or not event.get("title", "").strip()
        ):
            raise ValueError("Localist response contains an event without id/title")
        start = event.get("first_date") or event.get("start")
        has_start = isinstance(start, str) and bool(start.strip())
        if not has_start:
            instances = event.get("event_instances")
            has_start = isinstance(instances, list) and any(
                isinstance(item, dict)
                and isinstance(item.get("event_instance"), dict)
                and isinstance(item["event_instance"].get("start"), str)
                and bool(item["event_instance"]["start"].strip())
                for item in instances
            )
        if not has_start:
            raise ValueError("Localist response contains an event without a start")
        events.append(event)
    return events


def fetch_all() -> tuple[int, int]:
    """Walk the paginated API. Returns (total_events, new_events)."""
    s = _session()
    first = _fetch_page(s, 1)
    page_info = first.get("page")
    if not isinstance(page_info, dict):
        raise ValueError("Localist response is missing page metadata")
    total = page_info.get("total")
    size = page_info.get("size")
    if (
        not isinstance(total, int)
        or isinstance(total, bool)
        or total <= 0
        or not isinstance(size, int)
        or isinstance(size, bool)
        or size <= 0
    ):
        raise ValueError("Localist response has invalid or empty page metadata")
    pages = max(1, -(-total // size))  # ceil
    log.info("Localist reports %d events across %d page(s)", total, pages)

    seen = new = 0
    seen_ids: set[str] = set()

    def handle_payload(payload: dict[str, Any]) -> None:
        nonlocal seen, new
        for ev in _events_from_payload(payload):
            seen += 1
            seen_ids.add(str(ev["id"]))
            if _write_event(ev):
                new += 1

    handle_payload(first)
    for page in range(2, pages + 1):
        # Polite jitter — Localist isn't IG, but no reason to hammer it.
        time.sleep(random.uniform(1.0, 2.0))
        handle_payload(_fetch_page(s, page))

    if len(seen_ids) != total:
        raise ValueError(
            f"Localist snapshot incomplete: expected {total} unique events, got {len(seen_ids)}"
        )

    pruned = _prune_missing_events(seen_ids)
    if pruned:
        log.info("UCR events: pruned %d stale raw file(s)", pruned)

    return seen, new


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ensure_dirs()
    seen, new = fetch_all()
    log.info("UCR events: %d seen, %d new", seen, new)


if __name__ == "__main__":
    main()
