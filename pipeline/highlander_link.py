"""Fetch events from highlanderlink.ucr.edu (CampusLabs Engage) via its JSON API.

Writes one JSON file per event to data/raw/highlander_link/<id>.json.

HighlanderLink events are mutable (descriptions get edited, locations change),
so the raw file is overwritten every run — the latest fetch wins, same as the
Localist scraper. Also like Localist, the snapshot is buffered in memory and
only flushed once the whole walk succeeds: a partial rewrite would leave the
raw directory a mix of old and new events, which `run.py` cannot distinguish
from a clean previous snapshot.

The public Engage search endpoint backs the events page React app. No auth
needed for `visibility=Public` events. It returns Azure Search-style results;
we only care about the `value[]` documents.
"""
from __future__ import annotations

import json
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any

import requests

from config import RAW_DIR, ensure_dirs

log = logging.getLogger("pipeline.highlander_link")

API_BASE = "https://highlanderlink.ucr.edu/api/discovery/event/search"
PER_PAGE = 100
SOURCE_DIR = RAW_DIR / "highlander_link"

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
            "Referer": "https://highlanderlink.ucr.edu/events",
        }
    )
    return s


def _fetch_page(s: requests.Session, skip: int, ends_after: str) -> dict[str, Any]:
    params = {
        "endsAfter": ends_after,
        "orderByField": "endsOn",
        "orderByDirection": "ascending",
        "status": "Approved",
        "take": PER_PAGE,
        "skip": skip,
    }
    r = s.get(API_BASE, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _write_event(event: dict[str, Any]) -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    path = SOURCE_DIR / f"{event['id']}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(event, f, indent=2, sort_keys=True, ensure_ascii=False)


def _prune_missing_events(seen_ids: set[str]) -> int:
    """Remove raw HighlanderLink files absent from a completed source scrape."""
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
    events = payload.get("value")
    if not isinstance(events, list):
        raise ValueError("HighlanderLink response is missing a value list")
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("HighlanderLink response contains a malformed event")
        if (
            event.get("id") is None
            or not isinstance(event.get("name"), str)
            or not event.get("name", "").strip()
            or not isinstance(event.get("startsOn"), str)
            or not event.get("startsOn", "").strip()
        ):
            raise ValueError("HighlanderLink response contains an incomplete event")
    return events


def _collect_snapshot() -> dict[str, dict[str, Any]]:
    """Walk every page into memory. Raises unless the full snapshot arrives."""
    s = _session()
    ends_after = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    first = _fetch_page(s, skip=0, ends_after=ends_after)
    total = first.get("@odata.count")
    if (
        not isinstance(total, int)
        or isinstance(total, bool)
        or total <= 0
    ):
        raise ValueError("HighlanderLink response has an invalid or empty event count")
    pages = max(1, -(-total // PER_PAGE))
    log.info("HighlanderLink reports %d events across %d page(s)", total, pages)

    events: dict[str, dict[str, Any]] = {}

    def absorb(payload: dict[str, Any], page: int) -> None:
        entries = _events_from_payload(payload)
        if not entries:
            raise ValueError(f"HighlanderLink page {page} of {pages} came back empty")
        for ev in entries:
            events[str(ev["id"])] = ev

    absorb(first, 1)
    for page in range(1, pages):
        time.sleep(random.uniform(1.0, 2.0))
        absorb(_fetch_page(s, skip=page * PER_PAGE, ends_after=ends_after), page + 1)

    if len(events) != total:
        raise ValueError(
            "HighlanderLink snapshot incomplete: "
            f"expected {total} unique events, got {len(events)}"
        )
    return events


def fetch_all() -> tuple[int, int]:
    """Fetch a complete snapshot, then swap it in. Returns (total, new)."""
    events = _collect_snapshot()

    existing = (
        {path.stem for path in SOURCE_DIR.glob("*.json")} if SOURCE_DIR.exists() else set()
    )
    for ev in events.values():
        _write_event(ev)
    new = len(set(events) - existing)

    pruned = _prune_missing_events(set(events))
    if pruned:
        log.info("HighlanderLink events: pruned %d stale raw file(s)", pruned)

    return len(events), new


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ensure_dirs()
    seen, new = fetch_all()
    log.info("HighlanderLink events: %d seen, %d new", seen, new)


if __name__ == "__main__":
    main()
