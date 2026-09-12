"""On-disk archive of collected Instagram feed posts.

Separated from `scrape_posts` so that reading the archive — which extraction,
assessment, and reconciliation all do — does not drag in Instaloader and the
collector's session machinery. Nothing here talks to Instagram.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from config import POSTS_DIR

log = logging.getLogger("pipeline.post_archive")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    temporary.replace(path)


def media_key(url: Any) -> str:
    """A stable identity for one image, independent of its signed CDN URL.

    Instagram re-signs media URLs constantly (`oh`, `oe`, `_nc_gid`, `stp`…),
    so the URL itself changes on every fetch while the media does not. The
    path's filename is the part Instagram keeps stable, and keying OCR on it is
    what makes a refreshed URL cost nothing.
    """
    if not isinstance(url, str) or not url.strip():
        return ""
    path = urlsplit(url.strip()).path
    name = path.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0] or path


def post_path(handle: str, media_id: str) -> Path:
    return POSTS_DIR / handle / f"{media_id}.json"


def write_post(record: dict[str, Any]) -> str:
    """Save a post locally. Returns "new", "updated", or "unchanged".

    A re-observed post keeps its original `first_seen_at` and takes the newer
    caption and media URLs: a club editing a caption is a real correction, and
    the refreshed URLs are what a later flyer download needs. `fetched_at`
    alone never counts as a change — otherwise every run would rewrite every
    file and report the whole archive as updated.
    """
    path = post_path(record["handle"], record["media_id"])
    saved: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = read_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            loaded = None
        if isinstance(loaded, dict):
            saved = loaded
    merged = {**record, "first_seen_at": saved.get("first_seen_at") or record["fetched_at"]}
    if not saved:
        write_json(path, merged)
        return "new"
    volatile = {"fetched_at"}
    if all(saved.get(key) == value for key, value in merged.items() if key not in volatile):
        return "unchanged"
    write_json(path, merged)
    return "updated"


def iter_local_posts(handles: Iterable[str] | None = None) -> Iterable[dict[str, Any]]:
    """Walk the post archive. `handles` filters to the current roster."""
    if not POSTS_DIR.exists():
        return
    allowed = set(handles) if handles is not None else None
    for handle_dir in sorted(POSTS_DIR.iterdir()):
        if not handle_dir.is_dir():
            continue
        if allowed is not None and handle_dir.name not in allowed:
            continue
        for path in sorted(handle_dir.glob("*.json")):
            try:
                record = read_json(path)
            except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                log.warning("skipping malformed post file: %s", path)
                continue
            if isinstance(record, dict) and record.get("media_id"):
                yield record
