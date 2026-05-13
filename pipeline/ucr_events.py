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


def fetch_all() -> tuple[int, int]:
    """Walk the paginated API. Returns (total_events, new_events)."""
    s = _session()
    first = _fetch_page(s, 1)
    total = first.get("page", {}).get("total", 0)
    size = first.get("page", {}).get("size", PER_PAGE)
    pages = max(1, -(-total // size))  # ceil
    log.info("Localist reports %d events across %d page(s)", total, pages)

    seen = new = 0

    def handle_payload(payload: dict[str, Any]) -> None:
        nonlocal seen, new
        for entry in payload.get("events", []):
            ev = entry.get("event") if isinstance(entry, dict) else None
            if not ev or "id" not in ev:
                continue
            seen += 1
            if _write_event(ev):
                new += 1

    handle_payload(first)
    for page in range(2, pages + 1):
        # Polite jitter — Localist isn't IG, but no reason to hammer it.
        time.sleep(random.uniform(1.0, 2.0))
        try:
            handle_payload(_fetch_page(s, page))
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
    log.info("UCR events: %d seen, %d new", seen, new)


if __name__ == "__main__":
    main()
