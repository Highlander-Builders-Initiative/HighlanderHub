"""Fetch events from events.ucr.edu (Localist platform) via its JSON API.

Writes one JSON file per event to data/raw/ucr_events/<id>.json.

Unlike Instagram stories (which are immutable), Localist events are mutable —
descriptions get edited, locations change, etc. We always overwrite the raw
file so the on-disk copy reflects Localist's current state.

The whole snapshot is buffered in memory and only flushed to disk once every
page has been fetched and validated. A mid-walk failure must leave the previous
snapshot untouched — `run.py` falls back to it, so a half-rewritten directory
would silently mix months of partial scrapes together.

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


def _write_event(event: dict[str, Any]) -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    path = SOURCE_DIR / f"{event['id']}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(event, f, indent=2, sort_keys=True, ensure_ascii=False)


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


def _page_count(payload: dict[str, Any]) -> int:
    """Number of pages in the result set.

    Localist's `page.total` is the PAGE count, not the event count — page 9 of
    9 comes back full and page 10 comes back empty. Dividing it by `page.size`
    (as if it were an event count) floors to 1 and silently truncates the scrape
    after a single page.
    """
    page_info = payload.get("page")
    if not isinstance(page_info, dict):
        raise ValueError("Localist response is missing page metadata")
    total = page_info.get("total")
    if not isinstance(total, int) or isinstance(total, bool) or total <= 0:
        raise ValueError("Localist response has invalid or empty page metadata")
    return total


def _instance_entries(event: dict[str, Any]) -> list[dict[str, Any]]:
    entries = event.get("event_instances")
    if not isinstance(entries, list):
        return []
    return [
        entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("event_instance"), dict)
    ]


def _merge_occurrence(prior: dict[str, Any], latest: dict[str, Any]) -> dict[str, Any]:
    """Union two entries for the same event id.

    Localist paginates by OCCURRENCE: a weekly event returns one entry per
    session, and each entry carries only its own session in `event_instances`.
    Last-write-wins would leave the raw file holding one arbitrary occurrence,
    which is what `normalize_events` then turns into a single row for a series
    that actually runs a dozen times. Every field but `event_instances` is
    identical across the copies, so keep the newest copy and union the instances.
    """
    merged = dict(latest)
    by_key: dict[str, dict[str, Any]] = {}
    for source in (prior, latest):
        for entry in _instance_entries(source):
            inner = entry["event_instance"]
            key = str(inner.get("id") or inner.get("start") or "")
            if key:
                by_key.setdefault(key, entry)
    merged["event_instances"] = sorted(
        by_key.values(),
        key=lambda entry: str(entry["event_instance"].get("start") or ""),
    )
    return merged


def _collect_snapshot() -> dict[str, dict[str, Any]]:
    """Walk every page into memory. Raises unless the full snapshot arrives."""
    s = _session()
    first = _fetch_page(s, 1)
    pages = _page_count(first)
    log.info("Localist reports %d page(s) of events", pages)

    events: dict[str, dict[str, Any]] = {}

    def absorb(payload: dict[str, Any], page: int) -> None:
        entries = _events_from_payload(payload)
        if not entries:
            raise ValueError(f"Localist page {page} of {pages} came back empty")
        for ev in entries:
            eid = str(ev["id"])
            prior = events.get(eid)
            events[eid] = ev if prior is None else _merge_occurrence(prior, ev)

    absorb(first, 1)
    for page in range(2, pages + 1):
        # Polite jitter — Localist isn't IG, but no reason to hammer it.
        time.sleep(random.uniform(1.0, 2.0))
        absorb(_fetch_page(s, page), page)

    if not events:
        raise ValueError("Localist snapshot is empty")
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
        log.info("UCR events: pruned %d stale raw file(s)", pruned)

    return len(events), new


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ensure_dirs()
    seen, new = fetch_all()
    log.info("UCR events: %d seen, %d new", seen, new)


if __name__ == "__main__":
    main()
