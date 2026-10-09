"""Withdraw listings whose Instagram post was deleted before the event.

A club that changes an event's time often deletes the old post and publishes a
new one. Collection only ever sees new posts, so the old listing would stay up
beside its replacement. This stage looks each source post up once, shortly
before its event, and retires the listing when Instagram says it is gone.

Deletion is only believed when the actor names it: an explicit "deleted" error
row for that exact post. A missing row, a rate limit or an outage is unknown and
changes nothing. A listing is withdrawn after two such confirmations in
separate runs, so one bad response cannot remove a live event.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone

from apify_posts import ApifyClient, CollectionDeferred, charge_limit_reason
from config import DATA_DIR
from post_archive import iso, read_json, write_json

log = logging.getLogger("pipeline.post_recheck")

STATE_FILE = DATA_DIR / "post_rechecks.json"
RUN_FILE = DATA_DIR / "post_recheck_run.json"
LOOKAHEAD_DAYS = 3
CONFIRMATIONS = 2
# The next scheduled run is 8h away; never confirm twice inside one run window.
CONFIRM_AFTER = timedelta(hours=6)
BATCH_SIZE = 50
# A lookup ceiling, far above the ~$0.0015 per post the actor charges.
MAX_CHARGE_USD = float(os.environ.get("APIFY_RECHECK_MAX_CHARGE_USD", "0.25"))
DELETED = re.compile(r"deleted|not found|no longer available|does not exist", re.I)
POST_URL = re.compile(r"instagram\.com/(?:[^/]+/)?(?:p|reel|reels)/([A-Za-z0-9_-]+)")


def lookahead_days() -> int:
    return int(os.environ.get("APIFY_RECHECK_DAYS", LOOKAHEAD_DAYS))


def due_sources(events: list[dict], registry: dict[str, dict], state: dict, now: datetime) -> dict[str, list[str]]:
    """Source keys that own a listing starting soon and still need a look.

    Returns {source_key: [event ids]}. Finished checks and withdrawn posts drop out.
    """
    horizon = now + timedelta(days=lookahead_days())
    soon = set()
    for event in events:
        try:
            start = datetime.fromisoformat(str(event["starts_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if now <= start <= horizon:
            soon.add(event["id"])
    due = {}
    for key, row in registry.items():
        if (row.get("assessment") or {}).get("deleted"):
            continue
        owned = sorted(soon & set(row.get("event_ids") or []))
        if not owned:
            continue
        seen = state.get(key.rsplit(":", 1)[-1]) or {}
        if seen.get("status") == "present":
            continue
        checked = seen.get("checked_at")
        if seen.get("status") == "missing" and checked and \
                now - datetime.fromisoformat(checked) < CONFIRM_AFTER:
            continue
        due[key] = owned
    return due


def classify(rows: list[dict], codes: list[str]) -> dict[str, str]:
    """present / missing for the posts the actor spoke about; others stay out."""
    found = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        node = row.get("data") if isinstance(row.get("data"), dict) else {}
        code = node.get("code") or node.get("shortcode")
        if code in codes and not row.get("error") and row.get("kind") in ("post", "reel"):
            found[code] = "present"
            continue
        match = POST_URL.search(str(row.get("input") or ""))
        if match and match.group(1) in codes and DELETED.search(str(row.get("error") or "")):
            found.setdefault(match.group(1), "missing")
    return found


def withdrawal(source_key: str, row: dict, now: datetime) -> dict:
    """An update that publishes nothing for the source, retiring its listings."""
    return {"source_key": source_key, "origin": "instagram",
            "assessment": {"status": "complete", "deleted": True, "deleted_at": iso(now),
                           "reason": "Source post was deleted from Instagram"},
            "rows": [], "known_event_ids": sorted(set(row.get("event_ids") or []))}


def shortcodes(media_ids: list[str]) -> dict[str, str]:
    from db import client
    found = {}
    for i in range(0, len(media_ids), 200):
        chunk = media_ids[i:i + 200]
        for row in client().table("instagram_posts").select("media_id,shortcode").in_("media_id", chunk).execute().data or []:
            if row.get("shortcode"):
                found[str(row["media_id"])] = row["shortcode"]
    return found


def main() -> None:
    import assessed_events
    from db import client
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=lookahead_days())
    events = (client().table("events").select("id,starts_at").eq("source", "instagram")
              .gte("starts_at", iso(now)).lte("starts_at", iso(horizon)).execute().data or [])
    registry = assessed_events.load_registry()
    state = read_json(STATE_FILE) if STATE_FILE.exists() else {}
    due = due_sources(events, registry, state, now)
    if not due:
        log.info("post recheck: nothing due")
        return
    media_ids = [key.rsplit(":", 1)[-1] for key in due]
    codes = shortcodes(media_ids)
    by_code = {codes[m]: m for m in media_ids if m in codes}
    if len(by_code) < len(media_ids):
        log.warning("post recheck: %d post(s) have no shortcode and were skipped", len(media_ids) - len(by_code))
    token = os.environ.get("APIFY_TOKEN", "")
    api = ApifyClient(token, RUN_FILE)
    results: dict[str, str] = {}
    pending = sorted(by_code)
    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i:i + BATCH_SIZE]
        run, rows = api.details(batch, max_charge=MAX_CHARGE_USD, timeout=600)
        details_file = RUN_FILE.with_name(RUN_FILE.stem + "-details.json")
        write_json(details_file, {**read_json(details_file), "consumed": True})
        # Count against the lookup's own ceiling; a charge-limited run may
        # have stopped before reaching every post, so nothing can be concluded.
        if run.get("status") != "SUCCEEDED":
            raise RuntimeError(f"Post recheck run {run.get('id')} ended {run.get('status')}")
        reason = charge_limit_reason(run, MAX_CHARGE_USD, len(rows), details=True)
        if reason:
            raise CollectionDeferred(f"Post recheck: {reason}")
        batch_result = classify(rows, set(pending))
        gone = sum(1 for v in batch_result.values() if v == "missing")
        if len(batch) >= 4 and gone * 2 > len(batch):
            # Posts this old almost never vanish together; the lookup is broken.
            raise RuntimeError(f"Post recheck: {gone} of {len(batch)} posts reported deleted; "
                               "treating the response as an outage and changing nothing")
        results.update(batch_result)

    updates = []
    for code, outcome in results.items():
        media_id = by_code[code]
        key = f"instagram:post:{media_id}"
        entry = state.get(media_id) or {}
        if outcome == "present":
            state[media_id] = {"status": "present", "checked_at": iso(now)}
            continue
        misses = entry.get("misses", 0) + 1
        state[media_id] = {"status": "missing", "misses": misses, "checked_at": iso(now)}
        log.info("post %s (%s): reported deleted (%d/%d)", media_id, code, misses, CONFIRMATIONS)
        if misses >= CONFIRMATIONS:
            updates.append(withdrawal(key, registry[key], now))
            state[media_id]["status"] = "withdrawn"
    write_json(STATE_FILE, state)
    if updates:
        log.info("post recheck: withdrawing %d deleted post(s): %s", len(updates),
                 ", ".join(u["source_key"] for u in updates))
        log.info("Assessed publication: %s", assessed_events.publish(updates))
    log.info("post recheck: %d looked up, %d present, %d reported deleted, %d withdrawn",
             len(results), sum(v == "present" for v in results.values()),
             sum(v == "missing" for v in results.values()), len(updates))
