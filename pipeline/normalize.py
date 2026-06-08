"""Roll raw/<handle>/*.json into the Supabase `stories` table.

Decoupling scrape and normalize lets the frontend read a stable table
without racing the scraper. The raw archive on disk is the durable record
(stories expire from IG in 24h); Supabase is the queryable view.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import RAW_DIR, STORIES_WINDOW_DAYS, ensure_dirs, load_accounts
from db import upsert_batched

log = logging.getLogger("pipeline.normalize")


def _load_account_meta() -> dict[str, dict[str, Any]]:
    return {a["handle"]: a for a in load_accounts()}


def collect(known_handles: set[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not RAW_DIR.exists():
        return items
    for handle_dir in sorted(RAW_DIR.iterdir()):
        if not handle_dir.is_dir():
            continue
        # Skip raw dirs that belong to non-IG sources (ucr_events, etc.) —
        # those are handled by normalize_events.py.
        if handle_dir.name not in known_handles:
            continue
        for path in handle_dir.glob("*.json"):
            try:
                with path.open(encoding="utf-8") as f:
                    items.append(json.load(f))
            except json.JSONDecodeError:
                log.warning("skipping malformed file: %s", path)
    return items


def _to_story_row(item: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "handle": item["handle"],
        "account_label": meta.get("label"),
        "account_category": meta.get("category"),
        "owner_userid": item.get("owner_userid"),
        "owner_username": item.get("owner_username"),
        "typename": item.get("typename"),
        "is_video": bool(item.get("is_video", False)),
        "posted_at": item["posted_at"],
        "expires_at": item.get("expires_at"),
        "image_url": item.get("image_url"),
        "video_url": item.get("video_url"),
        "caption": item.get("caption"),
        "caption_mentions": item.get("caption_mentions") or [],
        "story_cta_url": item.get("story_cta_url"),
        "permalink": item.get("permalink"),
    }


def _within_window(posted_at: Any, cutoff: datetime) -> bool:
    """True if the story was posted on/after the cutoff. Missing or unparseable
    timestamps are kept — we'd rather re-upsert than silently drop a story."""
    if not isinstance(posted_at, str):
        return True
    text = posted_at.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed >= cutoff


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ensure_dirs()
    meta = _load_account_meta()
    items = collect(set(meta.keys()))

    if STORIES_WINDOW_DAYS > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=STORIES_WINDOW_DAYS)
        kept = [it for it in items if _within_window(it.get("posted_at"), cutoff)]
        log.info(
            "stories window: %d/%d posted within last %dd (older snapshots already "
            "in Supabase from prior runs; skipping re-upsert)",
            len(kept),
            len(items),
            STORIES_WINDOW_DAYS,
        )
        items = kept

    by_id: dict[str, dict[str, Any]] = {}
    for it in items:
        by_id[it["id"]] = _to_story_row(it, meta.get(it["handle"], {}))

    written = upsert_batched("stories", list(by_id.values()))
    log.info("Wrote %d stories to Supabase", written)


if __name__ == "__main__":
    main()
