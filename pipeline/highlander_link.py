"""Fetch events from highlanderlink.ucr.edu (CampusLabs Engage) via its JSON API.

Writes one JSON file per event to data/raw/highlander_link/<id>.json.

HighlanderLink events are mutable (descriptions get edited, locations change),
so the raw file is overwritten every run — the latest fetch wins, same as the
Localist scraper.

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


def _write_event(event: dict[str, Any]) -> bool:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    path = SOURCE_DIR / f"{event['id']}.json"
    is_new = not path.exists()
    with path.open("w", encoding="utf-8") as f:
        json.dump(event, f, indent=2, sort_keys=True, ensure_ascii=False)
    return is_new


def fetch_all() -> tuple[int, int]:
    """Walk paginated results. Returns (total_events, new_events)."""
    s = _session()
    ends_after = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    first = _fetch_page(s, skip=0, ends_after=ends_after)
    total = first.get("@odata.count") or 0
    pages = max(1, -(-total // PER_PAGE))
    log.info("HighlanderLink reports %d events across %d page(s)", total, pages)

    seen = new = 0

    def handle_payload(payload: dict[str, Any]) -> None:
        nonlocal seen, new
        for ev in payload.get("value", []):
            if not isinstance(ev, dict) or "id" not in ev:
                continue
            seen += 1
            if _write_event(ev):
                new += 1

    handle_payload(first)
    for page in range(1, pages):
        time.sleep(random.uniform(1.0, 2.0))
        try:
            handle_payload(_fetch_page(s, skip=page * PER_PAGE, ends_after=ends_after))
        except requests.HTTPError as e:
            log.warning("page %d failed: %s — stopping pagination", page, e)
            break

    return seen, new


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ensure_dirs()
    seen, new = fetch_all()
    log.info("HighlanderLink events: %d seen, %d new", seen, new)


if __name__ == "__main__":
    main()
