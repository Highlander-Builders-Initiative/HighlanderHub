"""Fetch Instagram feed posts for the configured accounts.

Writes one JSON file per post to data/posts/<handle>/<media_id>.json and a
durable copy to Supabase. Unlike stories, posts do not expire from Instagram,
so the archive is a cache rather than the only record — but it is still the
thing that makes a daily run cheap, because a post already on disk costs no
OCR and no model call.

Collection is forward-only. Each account records an activation timestamp
before its first fetch and never imports anything published before it, so
turning the collector on does not backfill a club's history — including an old
post that gets pinned to the top of the profile later.
"""
from __future__ import annotations

import json
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple

import instaloader
from instaloader.exceptions import (
    # ConnectionException is the base of TooManyRequests/NotFound and is
    # deliberately *not* fatal on its own — see _classify_failure.
    ConnectionException,
    LoginRequiredException,
    PrivateProfileNotFollowedException,
    ProfileNotExistsException,
    QueryReturnedBadRequestException,
    QueryReturnedForbiddenException,
    QueryReturnedNotFoundException,
    TooManyRequestsException,
)

from config import POST_CHECKPOINTS_FILE, POST_OVERLAP_DAYS, ensure_post_dirs
from post_archive import (
    hydrate_local_posts,
    iso as _iso,
    iter_local_posts,
    media_key,
    parse_instant as _parse_instant,
    read_json as _read_json,
    utc_now as _utc_now,
    write_json as _write_json,
    write_post,
)
from scrape import (
    _attach_http_error_logger,
    _load_scrape_accounts,
    _login,
    _persist_rotated_session,
)

log = logging.getLogger("pipeline.scrape_posts")

# Instagram lets a profile pin posts to the top of its feed regardless of age,
# and `Post.is_pinned` is documented in instaloader 4.15 as "now likely returns
# always false". Instaloader's own downloader solves this by never letting the
# first few entries terminate a scan (`possibly_pinned=3`); follow that
# convention rather than trusting the flag. Pinned entries are still evaluated
# on their own merits — they just cannot decide where the scan stops.
POSSIBLY_PINNED = 3

# Posts are fetched one profile at a time: unlike stories there is no batched
# endpoint, so a run is one request per account plus pagination. Instaloader's
# own rate controller already paces the individual requests; this jitter keeps
# the per-account cadence from looking metronomic on top of it.
ACCOUNT_SLEEP_RANGE = (3.0, 9.0)

# A scan walks pages until it reaches this boundary. Bounded so one account
# with a deep feed and a broken checkpoint cannot spend the whole run.
MAX_POSTS_PER_ACCOUNT = 60


class InstagramPostsBlocked(RuntimeError):
    """Authentication challenge or rate limit: stop collecting this run."""


# ---------------------------------------------------------------- checkpoints


def load_local_checkpoints() -> dict[str, dict[str, Any]]:
    if not POST_CHECKPOINTS_FILE.exists():
        return {}
    try:
        saved = _read_json(POST_CHECKPOINTS_FILE)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        log.warning("post checkpoints unreadable (%s); treating as empty", exc)
        return {}
    entries = saved.get("accounts") if isinstance(saved, dict) else None
    return entries if isinstance(entries, dict) else {}


def write_local_checkpoints(checkpoints: dict[str, dict[str, Any]]) -> None:
    """Merge the given rows into the local cache, leaving untouched ones alone.

    Checkpoints are a keyed store, not a snapshot of one run. A pilot
    (`--handle acm.ucr`) resolves a single account, and writing the file from
    that run's handles would drop every other club's activation boundary — so
    the next full run would either re-walk from activation and re-admit the
    back catalogue, or re-activate at `now` and silently skip the interval the
    lost row had already claimed. The durable store never deletes on upsert;
    neither does this.
    """
    merged = load_local_checkpoints()
    merged.update(checkpoints)
    _write_json(
        POST_CHECKPOINTS_FILE,
        {"generated_at": _iso(_utc_now()), "accounts": merged},
    )


def _load_remote_checkpoints() -> dict[str, dict[str, Any]]:
    try:
        from db import client

        rows = (
            client()
            .table("instagram_post_checkpoints")
            .select("*")
            .execute()
            .data
            or []
        )
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - local cache still works.
        log.warning("post checkpoints: remote read failed: %s", exc)
        return {}
    return {str(row["handle"]): row for row in rows if row.get("handle")}


def _claim_remote_activation(entries: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Register activation for accounts that have never been collected.

    The RPC inserts only when absent and returns the stored rows, so a lost
    local cache — or two runs racing — can never move an existing activation
    boundary and re-admit a club's history.
    """
    if not entries:
        return {}
    try:
        from db import client

        stored = client().rpc("claim_post_activation", {"entries": entries}).execute().data
    except (Exception, SystemExit) as exc:  # noqa: BLE001
        log.warning("post checkpoints: activation claim failed: %s", exc)
        return {}
    return stored if isinstance(stored, dict) else {}


def resolve_checkpoints(
    handles: Iterable[str], now: datetime
) -> dict[str, dict[str, Any]]:
    """Merge local and durable checkpoints, activating new accounts once.

    The durable row wins for `activated_at`: it is the boundary that keeps
    history out, and a machine that lost `data/` must not re-activate at today
    and silently re-admit everything published since the real activation.
    """
    handles = sorted({handle for handle in handles if handle})
    local = load_local_checkpoints()
    checkpoints = {handle: dict(local.get(handle, {})) for handle in handles}
    for handle, row in _load_remote_checkpoints().items():
        if handle not in checkpoints:
            continue
        remote_activation = _parse_instant(row.get("activated_at"))
        if remote_activation is not None:
            checkpoints[handle]["activated_at"] = _iso(remote_activation)
        local_through = _parse_instant(checkpoints[handle].get("scanned_through"))
        remote_through = _parse_instant(row.get("scanned_through"))
        # The older of the two is the only safe resume point: whichever side
        # is behind still has an uncollected interval to re-walk.
        through = min([value for value in (local_through, remote_through) if value], default=None)
        if through is not None:
            checkpoints[handle]["scanned_through"] = _iso(through)

    fresh = [handle for handle in handles if not checkpoints[handle].get("activated_at")]
    claimed = _claim_remote_activation(
        [{"handle": handle, "activated_at": _iso(now)} for handle in fresh]
    )
    for handle in fresh:
        stored = _parse_instant((claimed.get(handle) or {}).get("activated_at"))
        checkpoints[handle]["activated_at"] = _iso(stored or now)
        if handle in claimed:
            log.info("post collection activated for %s at %s", handle, checkpoints[handle]["activated_at"])
        else:
            # Activation could not be made durable. Record it locally so the
            # run still refuses history, and re-claim on the next run.
            log.warning(
                "%s: activation is local-only this run (durable store unavailable); "
                "the boundary will be confirmed on the next successful run",
                handle,
            )
    write_local_checkpoints(checkpoints)
    return checkpoints


def scan_boundary(checkpoint: dict[str, Any], now: datetime) -> datetime:
    """The oldest publication time this scan will accept.

    Discovery re-walks a fixed overlap behind the last successful scan so an
    interrupted run, a late edit, or clock skew cannot open a permanent hole —
    but never past activation, which is absolute.
    """
    activation = _parse_instant(checkpoint.get("activated_at")) or now
    through = _parse_instant(checkpoint.get("scanned_through"))
    if through is None:
        return activation
    return max(activation, through - timedelta(days=POST_OVERLAP_DAYS))


# ------------------------------------------------------------------- records


def _serialize_media(post: Any) -> list[dict[str, Any]]:
    """Ordered slide metadata. Carousel order is event evidence order."""
    entries: list[dict[str, Any]] = []
    if post.typename == "GraphSidecar":
        for index, node in enumerate(post.get_sidecar_nodes()):
            # Video nodes still expose a JPEG cover; OCR that still, like stories.
            url = node.display_url
            entries.append({
                "index": index,
                "is_video": bool(node.is_video),
                "image_url": url,
                "media_key": media_key(url) or f"{post.mediaid}_{index}",
            })
        if entries:
            return entries
    url = post.url
    return [{
        "index": 0,
        "is_video": bool(post.is_video),
        "image_url": url,
        "media_key": media_key(url) or f"{post.mediaid}_0",
    }]


def serialize_post(post: Any, handle: str, *, seen_at: datetime) -> dict[str, Any]:
    media = _serialize_media(post)
    caption = post.caption
    return {
        "media_id": str(post.mediaid),
        "handle": handle,
        "owner_username": str(getattr(post, "owner_username", "") or handle).lower(),
        "owner_userid": getattr(post, "owner_id", None),
        "shortcode": post.shortcode,
        "permalink": f"https://www.instagram.com/p/{post.shortcode}/",
        "posted_at": _iso(post.date_utc.replace(tzinfo=timezone.utc)),
        "typename": post.typename,
        "caption": caption,
        "caption_mentions": list(getattr(post, "caption_mentions", []) or []),
        "media": media,
        "has_video": any(entry["is_video"] for entry in media),
        "fetched_at": _iso(seen_at),
    }


def write_remote_posts(records: list[dict[str, Any]]) -> None:
    """Mirror raw posts durably. Raises so a scan cannot advance past a loss."""
    if not records:
        return
    from db import upsert_batched

    upsert_batched(
        "instagram_posts",
        [
            {
                "media_id": record["media_id"],
                "handle": record["handle"],
                "owner_username": record.get("owner_username"),
                "shortcode": record.get("shortcode"),
                "permalink": record.get("permalink"),
                "posted_at": record["posted_at"],
                "typename": record.get("typename"),
                "caption": record.get("caption"),
                "has_video": bool(record.get("has_video")),
                "media": record.get("media") or [],
                "record": record,
                "fetched_at": record["fetched_at"],
            }
            for record in records
        ],
        on_conflict="media_id",
    )


# -------------------------------------------------------------------- errors


def _classify_failure(exc: BaseException) -> str | None:
    """Name the failures that must stop Instagram collection outright.

    A rate limit or a challenged session does not get better by asking more
    accounts, and continuing would turn one throttle into a run-long pattern of
    rejected requests against an already-suspicious account.
    """
    if isinstance(exc, TooManyRequestsException):
        return "rate limited"
    if isinstance(exc, LoginRequiredException):
        return "login required"
    if isinstance(exc, QueryReturnedForbiddenException):
        return "forbidden (challenge or blocked session)"
    if isinstance(exc, QueryReturnedBadRequestException):
        # The same 400 the story scraper sees when a session goes stale.
        return "bad request (stale session or challenge)"
    return None


# ------------------------------------------------------------------ scanning


class AccountResult(NamedTuple):
    handle: str
    discovered: int
    updated: int
    unchanged: int
    scanned: int
    complete: bool
    media_ids: list[str]


def scan_account(
    L: instaloader.Instaloader,
    account: dict[str, Any],
    checkpoint: dict[str, Any],
    now: datetime,
) -> AccountResult:
    """Walk one profile's feed back to its boundary and save what is new.

    Raw writes are made durable before the caller advances the checkpoint, so
    an interrupted scan keeps what it collected and re-walks the rest next run.
    """
    handle = account["handle"]
    # `scan_boundary` is the single owner of the activation invariant: it never
    # returns an instant before the account was activated, so reaching the
    # boundary is the only stop condition this loop needs.
    boundary = scan_boundary(checkpoint, now)
    profile = instaloader.Profile.from_username(L.context, handle)

    records: list[dict[str, Any]] = []
    counts = {"new": 0, "updated": 0, "unchanged": 0}
    scanned = 0
    complete = False
    for number, post in enumerate(profile.get_posts(), start=1):
        published = post.date_utc.replace(tzinfo=timezone.utc)
        if published < boundary:
            # A pinned entry sits at the top of the feed no matter how old it
            # is, so it must not be read as "the feed is now older than the
            # boundary". Skip it and keep walking.
            if number <= POSSIBLY_PINNED:
                continue
            complete = True
            break
        scanned += 1
        record = serialize_post(post, handle, seen_at=now)
        records.append(record)
        counts[write_post(record)] += 1
        if scanned >= MAX_POSTS_PER_ACCOUNT:
            log.warning(
                "%s: stopped after %d posts without reaching %s; the remaining "
                "interval is retried next run",
                handle,
                scanned,
                boundary.date(),
            )
            break
    else:
        complete = True

    write_remote_posts(records)
    return AccountResult(
        handle, counts["new"], counts["updated"], counts["unchanged"], scanned,
        complete, [record["media_id"] for record in records],
    )


def refresh_candidates(now: datetime) -> dict[str, dict[str, Any]]:
    """Known posts still worth re-fetching, keyed by media ID.

    Two windows: anything inside the discovery overlap is re-walked by the scan
    itself, and outside it a post stays eligible only while the event it
    supports has not ended. After that a club's edits cannot change a listing
    that is already over, so the request would be pure cost.
    """
    try:
        from db import client, get_event_rows_by_ids

        rows = (
            client()
            .table("source_assessments")
            .select("source_key,event_ids")
            .like("source_key", "instagram:post:%")
            .execute()
            .data
            or []
        )
        event_ids = sorted({
            event_id for row in rows for event_id in (row.get("event_ids") or [])
        })
        live = {
            row["id"]
            for row in get_event_rows_by_ids(event_ids)
            if (_parse_instant(row.get("ends_at") or row.get("starts_at")) or now) > now
        }
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - refresh is an optimization.
        log.warning("post refresh: could not resolve supported events: %s", exc)
        return {}

    supporting = {
        str(row["source_key"]).removeprefix("instagram:post:")
        for row in rows
        if live & set(row.get("event_ids") or [])
    }
    return {
        record["media_id"]: record
        for record in iter_local_posts()
        if record["media_id"] in supporting and record.get("shortcode")
    }


def refresh_post(
    L: instaloader.Instaloader, record: dict[str, Any], now: datetime
) -> dict[str, Any]:
    """Re-fetch one known post by shortcode. Returns the refreshed record.

    Mirrored durably as well as locally: a corrected caption that only reached
    the local archive would be lost on restore, and the stale copy would keep
    publishing an event the club has since withdrawn.
    """
    post = instaloader.Post.from_shortcode(L.context, str(record["shortcode"]))
    refreshed = serialize_post(post, record["handle"], seen_at=now)
    write_post(refreshed)
    write_remote_posts([refreshed])
    return refreshed


def _sleep_between_accounts() -> None:
    time.sleep(random.uniform(*ACCOUNT_SLEEP_RANGE))


def main(handles: list[str] | None = None) -> None:
    """Collect posts. `handles` limits the run to named accounts, for a pilot."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ensure_post_dirs()
    # The archive is what decides which posts are new, which still need
    # refreshing, and which are already paid for — so a machine that lost
    # `data/` gets it back from the durable mirror before any of that is judged.
    hydrate_local_posts()

    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
    )
    L.context.user_agent = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Safari/605.1.15"
    )
    _login(L)
    _attach_http_error_logger(L)

    now = _utc_now()
    # `updated` is a post whose content changed where discovery already looked;
    # `refreshed` is a direct re-fetch of a post outside the discovery overlap.
    # Conflating them would hide how much the refresh pass actually costs.
    totals = {
        "accounts": 0, "scanned": 0, "discovered": 0, "updated": 0,
        "unchanged": 0, "refreshed": 0, "incomplete": 0, "errors": 0, "skipped": 0,
    }
    blocked: str | None = None
    try:
        accounts = _load_scrape_accounts(L)
        if handles:
            wanted = {handle.strip().lower() for handle in handles if handle.strip()}
            accounts = [account for account in accounts
                        if str(account.get("handle") or "").lower() in wanted]
            missing = wanted - {str(account.get("handle") or "").lower() for account in accounts}
            if missing:
                raise RuntimeError(
                    f"Not in the account roster: {', '.join(sorted(missing))}. "
                    "Post collection only covers accounts the run already follows."
                )
            log.info("Pilot run limited to %d account(s)", len(accounts))
        # Activation is claimed for exactly the accounts this run will fetch, so
        # a pilot does not silently start the clock for the whole roster.
        checkpoints = resolve_checkpoints(
            [str(account.get("handle") or "") for account in accounts], now)
        fetched: set[str] = set()

        for index, account in enumerate(accounts, start=1):
            handle = str(account.get("handle") or "")
            if not handle:
                totals["skipped"] += 1
                continue
            totals["accounts"] += 1
            checkpoint = checkpoints.setdefault(handle, {"activated_at": _iso(now)})
            try:
                result = scan_account(L, account, checkpoint, now)
            except (ProfileNotExistsException, PrivateProfileNotFollowedException,
                    QueryReturnedNotFoundException) as exc:
                totals["skipped"] += 1
                log.info("%s: no readable feed (%s)", handle, exc)
                continue
            except (Exception, SystemExit) as exc:  # noqa: BLE001 - per-account isolation.
                reason = _classify_failure(exc)
                totals["errors"] += 1
                if reason is not None:
                    blocked = f"{handle}: {reason}: {exc}"
                    break
                log.warning("%s: post scan failed: %s", handle, exc, exc_info=True)
                continue

            totals["scanned"] += result.scanned
            totals["discovered"] += result.discovered
            totals["updated"] += result.updated
            totals["unchanged"] += result.unchanged
            fetched.update(result.media_ids)
            if result.complete:
                # Only a completed scan whose raw writes landed may move the
                # checkpoint; anything else re-walks its interval next run.
                checkpoint["scanned_through"] = _iso(now)
            else:
                totals["incomplete"] += 1
            checkpoint["last_scan_at"] = _iso(now)
            checkpoint["last_status"] = "complete" if result.complete else "incomplete"
            log.info(
                "%s: %d in window, %d new, %d updated, %d unchanged%s",
                handle, result.scanned, result.discovered, result.updated,
                result.unchanged, "" if result.complete else " (incomplete)",
            )
            if index < len(accounts):
                _sleep_between_accounts()

        if blocked is None:
            # Posts outside the overlap that still back an upcoming event.
            # Anything already fetched by discovery this run is skipped.
            for media_id, record in sorted(refresh_candidates(now).items()):
                if media_id in fetched:
                    continue
                try:
                    refresh_post(L, record, now)
                except (Exception, SystemExit) as exc:  # noqa: BLE001
                    reason = _classify_failure(exc)
                    totals["errors"] += 1
                    if reason is not None:
                        blocked = f"refresh {media_id}: {reason}: {exc}"
                        break
                    log.warning("post %s: refresh failed: %s", media_id, exc)
                    continue
                totals["refreshed"] += 1
                fetched.add(media_id)
                _sleep_between_accounts()

        write_local_checkpoints(checkpoints)
        _write_remote_checkpoints(checkpoints)
        log.info("Done: %s", totals)
        if blocked is not None:
            raise InstagramPostsBlocked(
                f"Instagram post collection stopped early — {blocked}. Coverage is "
                "incomplete for this run; checkpoints were retained so the "
                "uncollected interval is re-walked once the session is healthy."
            )
        if totals["errors"]:
            raise RuntimeError(
                f"Instagram post collection hit {totals['errors']} failure(s); "
                "checkpoints for those accounts were retained."
            )
    finally:
        _persist_rotated_session(L)


def _write_remote_checkpoints(checkpoints: dict[str, dict[str, Any]]) -> None:
    rows = [
        {
            "handle": handle,
            "activated_at": entry["activated_at"],
            "scanned_through": entry.get("scanned_through"),
            "last_scan_at": entry.get("last_scan_at"),
            "last_status": entry.get("last_status"),
        }
        for handle, entry in checkpoints.items()
        if entry.get("activated_at")
    ]
    if not rows:
        return
    try:
        from db import upsert_batched

        upsert_batched("instagram_post_checkpoints", rows, on_conflict="handle")
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - local cache remains usable.
        log.warning("post checkpoints: remote write failed: %s", exc)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handle", action="append",
                        help="limit collection to this account (repeatable); for pilots")
    main(parser.parse_args().handle)
