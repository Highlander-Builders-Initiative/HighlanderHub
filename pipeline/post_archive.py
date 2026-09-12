"""On-disk archive of collected Instagram feed posts.

Separated from `scrape_posts` so that reading the archive — which extraction,
assessment, and reconciliation all do — does not drag in Instaloader and the
collector's session machinery. Nothing here talks to Instagram.

The archive is a cache of the durable `instagram_posts` mirror, and
`hydrate_local_posts` is the one direction that reads that mirror back. Without
it the mirror would be write-only, and a machine that lost `data/` would keep
only whatever the next scan's overlap window happens to re-walk.
"""
from __future__ import annotations

import json
import logging
import re
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


# --------------------------------------------------------- restore from mirror

# `instagram_posts` is the durable mirror of this archive. PostgREST caps an
# unbounded select, so the walk is paged, and the whole walk is bounded the way
# the other paginated reads are: a runaway table must not replace the run.
RESTORE_PAGE = 1000
MAX_RESTORE_ROWS = 1_000_000

# Mirrored identifiers become filesystem paths here. Instagram handles and media
# IDs are plain tokens; anything else is refused outright rather than sanitized
# into some other post's file.
_PATH_TOKEN = re.compile(r"[A-Za-z0-9_.-]+")


def _path_token(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text in {".", ".."} or not _PATH_TOKEN.fullmatch(text):
        return ""
    return text


def _mirrored_media_ids() -> set[str]:
    """Every media ID the durable mirror holds."""
    from db import client

    found: set[str] = set()
    for offset in range(0, MAX_RESTORE_ROWS, RESTORE_PAGE):
        page = (
            client()
            .table("instagram_posts")
            .select("media_id")
            .order("media_id")
            .range(offset, offset + RESTORE_PAGE - 1)
            .execute()
            .data
            or []
        )
        found.update(str(row["media_id"]) for row in page if row.get("media_id"))
        if len(page) < RESTORE_PAGE:
            return found
    raise RuntimeError("instagram_posts pagination exceeded its safety limit")


def _mirrored_rows(media_ids: list[str], batch_size: int = 200) -> Iterable[dict[str, Any]]:
    """Full mirrored records for the given IDs, in request-sized batches."""
    from db import client

    for offset in range(0, len(media_ids), batch_size):
        yield from (
            client()
            .table("instagram_posts")
            .select("media_id,handle,first_seen_at,record")
            .in_("media_id", media_ids[offset : offset + batch_size])
            .execute()
            .data
            or []
        )


def _restore_post(row: dict[str, Any]) -> bool:
    """Write one mirrored row into the archive. False if it is not usable."""
    record = row.get("record")
    if not isinstance(record, dict):
        log.warning("post archive: mirrored row %s carries no record", row.get("media_id"))
        return False
    handle = _path_token(row.get("handle") or record.get("handle"))
    media_id = _path_token(row.get("media_id") or record.get("media_id"))
    if not handle or not media_id:
        log.warning("post archive: refusing to restore %r/%r — not an archive path",
                    row.get("handle"), row.get("media_id"))
        return False
    restored = {**record, "handle": handle, "media_id": media_id}
    # `first_seen_at` is a column rather than part of the serialized record, and
    # it is what keeps a restored post from looking newly discovered.
    first_seen = (row.get("first_seen_at") or record.get("first_seen_at")
                  or record.get("fetched_at"))
    if first_seen:
        restored["first_seen_at"] = first_seen
    write_json(post_path(handle, media_id), restored)
    return True


def hydrate_local_posts() -> int:
    """Restore mirrored posts that are missing from the local archive.

    Every consumer of a post reads this archive and nothing else: extraction,
    the refresh pass that re-fetches a post while the event it backs is still
    upcoming, and reassessment. So mirroring raw posts to `instagram_posts` only
    protects a lost `data/` directory if something reads the mirror back — this
    is that read. Without it a restored machine keeps only what the next scan's
    overlap window happens to re-walk, and older posts still supporting live
    events silently stop being refreshed and reassessed.

    Gap-filling, never overwriting. A local file is written before the mirror row
    it produces, so it is at least as fresh; the mirror may restore a post but
    must not decide the contents of one already on disk. A file too corrupt for
    `iter_local_posts` to read counts as absent — replacing that is the point.

    Best-effort: an unreadable mirror costs coverage, not the run. Nor can this
    re-admit history, since the mirror only ever holds posts that some scan
    already accepted past its activation boundary.

    Returns the number of posts restored.
    """
    present = {str(record["media_id"]) for record in iter_local_posts()}
    try:
        missing = sorted(_mirrored_media_ids() - present)
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - the archive still works.
        log.warning("post archive: durable mirror unreadable (%s); this run has only "
                    "the local archive", exc)
        return 0
    if not missing:
        return 0
    log.info("post archive: restoring %d post(s) missing from %s", len(missing), POSTS_DIR)
    restored = 0
    try:
        for row in _mirrored_rows(missing):
            if _restore_post(row):
                restored += 1
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - keep whatever arrived.
        log.warning("post archive: restore stopped after %d post(s): %s", restored, exc)
    log.info("post archive: restored %d of %d missing post(s)", restored, len(missing))
    return restored
