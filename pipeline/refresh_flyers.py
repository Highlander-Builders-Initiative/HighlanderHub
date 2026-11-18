"""Fresh Instagram image links for upcoming events that show no flyer.

Opt-in (REFRESH_MISSING_FLYERS=true; the workflow's "refresh missing flyers"
input). Instagram's signed image links expire within days, and the pipeline
never re-requests an old post, so an upcoming event whose stored flyer was
lost (the November 2026 project move left ~220 of them) cannot be uploaded
again from its saved link. This stage looks those posts up through the Apify
single-post lookup (~$0.0015 a post), replaces the expired links in the post
archive, and leaves the rest to publication in the same run: extraction reuses
its OCR (the fingerprint ignores link signatures) and publication uploads the
missing flyers from the fresh links.

Only links are replaced, and only for slides whose signature-free media key
matches a slide already archived; captions and slides themselves are left to
the normal collector.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from apify_posts import ApifyClient, CollectionDeferred, charge_limit_reason, mirror
from config import DATA_DIR
from post_archive import (ArchiveIndex, hydrate_local_posts, iter_local_posts, media_key,
                          read_json, write_json, write_post)

log = logging.getLogger("pipeline.refresh_flyers")

RUN_FILE = DATA_DIR / "flyer_refresh_run.json"
BATCH_SIZE = 50
# A lookup ceiling per batch, far above the ~$0.0015 per post the actor charges.
MAX_CHARGE_USD = float(os.environ.get("REFRESH_FLYERS_MAX_CHARGE_USD", "0.25"))
# Bounds one run's spend whatever the backlog: 600 posts is about $1.
MAX_POSTS = int(os.environ.get("REFRESH_FLYERS_MAX_POSTS", "600"))


def enabled() -> bool:
    return os.environ.get("REFRESH_MISSING_FLYERS", "").strip().lower() == "true"


def _active(event: dict, now: datetime) -> bool:
    value = event.get("ends_at") or event.get("starts_at")
    try:
        instant = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return (instant if instant.tzinfo else instant.replace(tzinfo=timezone.utc)) >= now


def events_without_flyers(now: datetime) -> set[str]:
    """Upcoming Instagram listings whose image is not stored in this project."""
    from db import SUPABASE_URL, client

    stored = f"{(SUPABASE_URL or '').rstrip('/')}/storage/v1/object/public/event-flyers/"
    missing: set[str] = set()
    for offset in range(0, 1_000_000, 1000):
        rows = (client().table("events").select("id,image_url,starts_at,ends_at")
                .eq("source", "instagram").order("id").range(offset, offset + 999).execute().data or [])
        missing.update(row["id"] for row in rows
                       if _active(row, now) and not str(row.get("image_url") or "").startswith(stored))
        if len(rows) < 1000:
            return missing
    raise RuntimeError("Event pagination exceeded its safety limit")


def fresh_links(node: dict) -> dict[str, str]:
    """{media key: newest signed URL} for every slide of one looked-up post."""
    nodes = node.get("carousel_media") if node.get("media_type") == 8 else [node]
    links = {}
    for item in nodes if isinstance(nodes, list) else []:
        if not isinstance(item, dict):
            continue
        candidates = [entry for entry in ((item.get("image_versions2") or {}).get("candidates") or [])
                      if isinstance(entry, dict) and str(entry.get("url") or "").startswith("https://")]
        if not candidates and str(item.get("image_url") or "").startswith("https://"):
            candidates = [{"url": item["image_url"]}]
        if candidates:
            best = max(candidates, key=lambda entry: (entry.get("width") or 0) * (entry.get("height") or 0))
            links[media_key(best["url"])] = best["url"]
    return links


def relink(record: dict, links: dict[str, str]) -> dict | None:
    """The record with fresh slide links, or None when nothing matched or changed."""
    media = []
    changed = False
    for slide in record.get("media") or []:
        url = links.get(str(slide.get("media_key") or "")) if isinstance(slide, dict) else None
        if url and url != slide.get("image_url"):
            slide = {**slide, "image_url": url}
            changed = True
        media.append(slide)
    return {**record, "media": media} if changed else None


def main(*, archive: ArchiveIndex | None = None, now: datetime | None = None) -> dict:
    if not enabled():
        log.info("flyer refresh: off (REFRESH_MISSING_FLYERS is not true)")
        return {}
    import assessed_events

    now = now or datetime.now(timezone.utc)
    events = events_without_flyers(now)
    registry = assessed_events.load_registry(event_ids=events)
    media_ids = {key.rsplit(":", 1)[-1] for key, row in registry.items()
                 if key.startswith("instagram:post:") and events & set(row.get("event_ids") or [])}
    hydrate_local_posts(archive=archive or ArchiveIndex())
    by_code = {str(record["shortcode"]): record for record in iter_local_posts()
               if str(record.get("media_id")) in media_ids and record.get("shortcode")}
    codes = sorted(by_code)[:MAX_POSTS]
    stats = {"events_without_flyers": len(events), "posts": len(media_ids), "looked_up": 0,
             "refreshed": 0, "not_returned": 0, "skipped_over_limit": max(0, len(by_code) - len(codes))}
    if not codes:
        log.info("Flyer refresh: %s", stats)
        return stats
    api = ApifyClient(os.environ.get("APIFY_TOKEN", ""), RUN_FILE)
    details_file = RUN_FILE.with_name(RUN_FILE.stem + "-details.json")
    for start in range(0, len(codes), BATCH_SIZE):
        batch = codes[start:start + BATCH_SIZE]
        run, rows = api.details(batch, max_charge=MAX_CHARGE_USD, timeout=600)
        if run.get("status") != "SUCCEEDED":
            raise RuntimeError(f"Flyer refresh run {run.get('id')} ended {run.get('status')}")
        reason = charge_limit_reason(run, MAX_CHARGE_USD, len(rows), details=True)
        if reason:
            raise CollectionDeferred(f"Flyer refresh: {reason}")
        updated = []
        returned = set()
        for row in rows:
            node = row.get("data") if isinstance(row, dict) else None
            code = node.get("code") if isinstance(node, dict) else None
            # A resumed paid run may hold codes from an earlier backlog.
            if code not in by_code or row.get("error") or row.get("kind") not in ("post", "reel"):
                continue
            returned.add(code)
            record = relink(by_code[code], fresh_links(node))
            if record is not None:
                write_post(record)
                by_code[code] = record
                updated.append(record)
        if updated:
            mirror(updated)
        stats["looked_up"] += len(batch)
        stats["refreshed"] += len(updated)
        stats["not_returned"] += len(set(batch) - returned)
        # Saved before the paid run is marked consumed, so a replay only re-reads it.
        write_json(details_file, {**(read_json(details_file) if details_file.exists() else {}), "consumed": True})
    log.info("Flyer refresh: %s", stats)
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
