"""Fetch Instagram feed posts for the configured accounts.

Writes one JSON file per post to data/posts/<handle>/<media_id>.json and a
durable copy to Supabase. Posts do not expire from Instagram,
so the archive is a cache rather than the only record — but it is still the
thing that makes a daily run cheap, because a post already on disk costs no
OCR and no model call.

Normal collection is forward-only. Each account records an activation timestamp
before its first fetch and never imports anything published before it, so
turning the collector on does not backfill a club's history — including an old
post that gets pinned to the top of the profile later. An explicit maintenance
PIPELINE_POST_BACKFILL_SINCE setting overrides that scan boundary.
"""
from __future__ import annotations

import json
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, NamedTuple

import instaloader
from instaloader.exceptions import (
    ConnectionException,
    PrivateProfileNotFollowedException,
    ProfileNotExistsException,
    QueryReturnedNotFoundException,
)

import instagram_cooldown
from config import (POST_CHECKPOINTS_FILE, POST_OVERLAP_DAYS, POST_DISCOVERY_MODE,
                    POST_BACKFILL_SINCE, POST_EXTRACTED_DIR,
                    ensure_post_dirs, load_accounts)
from post_archive import (
    ArchiveIndex, hydrate_local_posts,
    iso as _iso,
    iter_local_posts,
    media_key,
    post_path,
    parse_instant as _parse_instant,
    read_json as _read_json,
    utc_now as _utc_now,
    write_json as _write_json,
    write_post,
)
from instagram_client import (
    PacedRateController,
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

# Posts are fetched one profile at a time. The default constructs the GraphQL
# feed iterator directly, avoiding a separate profile query. The opt-in direct-feed pilot uses the v1 endpoint.
# `PacedRateController` puts a floor under the individual requests; this jitter
# keeps the per-account cadence from looking metronomic on top of it.
ACCOUNT_SLEEP_RANGE = (5.0, 12.0)
DIRECT_FEED_MAX_ACCOUNTS = 5
DIRECT_FEED_MAX_PAGES = 3
# One unreadable account says nothing about the rest, so collection moves on.
# This many in a row points at the session, network or API instead: stop asking.
MAX_CONSECUTIVE_FAILURES = 5


class DirectFeedLimitReached(RuntimeError):
    """The pilot budget ended before coverage was established."""


class EmptyFeed(RuntimeError):
    """The profile shows no posts at all: none published, or private to us."""


class PartialCollection(RuntimeError):
    """Some accounts or posts failed on their own; the rest was collected."""


def _direct_feed_page(L: instaloader.Instaloader, handle: str,
                      user_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Use the live session through Instaloader's pacing and error handling.

    Keep response hooks and rotated cookies on the original session. Limit
    each page to one attempt so pushback cannot trigger automatic retries.
    Header and retry overrides apply only to this endpoint.
    """
    context = L.context
    session = context._session
    headers = session.headers.copy()
    attempts = context.max_connection_attempts
    fatal_codes = context.fatal_status_codes
    try:
        session.headers.update({
            "X-IG-App-ID": "936619743392459",
            "X-ASBD-ID": "198387",
            "User-Agent": context.user_agent,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://www.instagram.com/{handle}/",
        })
        context.max_connection_attempts = 1
        context.fatal_status_codes = list(set(fatal_codes) | {401, 403})
        return context.get_json(f"api/v1/feed/user/{user_id}/", params=params)
    finally:
        session.headers.clear()
        session.headers.update(headers)
        context.max_connection_attempts = attempts
        context.fatal_status_codes = fatal_codes


def _direct_feed_posts(L: instaloader.Instaloader, handle: str,
                       user_id: str) -> Iterable[Any]:
    """Bounded v1 pagination; malformed responses never establish coverage."""
    cursor = None
    seen_cursors: set[str] = set()
    pages = 0
    started = time.monotonic()
    try:
        for _ in range(DIRECT_FEED_MAX_PAGES):
            params: dict[str, Any] = {"count": 12}
            if cursor is not None:
                params["max_id"] = cursor
            pages += 1
            data = _direct_feed_page(L, handle, user_id, params)
            if (not isinstance(data, dict) or data.get("status") != "ok"
                    or not isinstance(data.get("items"), list)
                    or not isinstance(data.get("more_available"), bool)):
                raise RuntimeError(f"{handle}: malformed direct feed page")
            for item in data["items"]:
                yield instaloader.Post.from_iphone_struct(L.context, item)
            if not data["more_available"]:
                return
            cursor = data.get("next_max_id")
            if not isinstance(cursor, str) or not cursor or cursor in seen_cursors:
                raise RuntimeError(f"{handle}: missing or repeated direct feed cursor")
            seen_cursors.add(cursor)
        raise DirectFeedLimitReached(f"{handle}: direct feed page budget exhausted")
    finally:
        log.info("%s: direct feed attempted %d page(s) in %.1fs",
                 handle, pages, time.monotonic() - started)


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
    (`--handle acm_ucr`) resolves a single account, and writing the file from
    that run's handles would drop every other club's activation boundary. If
    the durable row is also missing, re-activation at `now` silently skips the
    interval the lost row had already claimed.
    """
    merged = load_local_checkpoints()
    merged.update(checkpoints)
    # Retire legacy sweep markers while preserving incremental checkpoints.
    for entry in merged.values():
        entry.pop("backfill", None)
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
    and silently skip everything published since the real activation.
    """
    handles = sorted({handle for handle in handles if handle})
    local = load_local_checkpoints()
    checkpoints = {handle: dict(local.get(handle, {})) for handle in handles}
    remote = _load_remote_checkpoints()
    # A local activation is not proof that its insert-only claim succeeded.
    # Retry absent durable rows using the original local boundary, even when
    # the read failed: the claim returns any existing row without moving it.
    unconfirmed = [handle for handle in handles
                   if _parse_instant((remote.get(handle) or {}).get("activated_at")) is None]
    remote.update(_claim_remote_activation([
        {"handle": handle,
         "activated_at": _iso(_parse_instant(checkpoints[handle].get("activated_at")) or now)}
        for handle in unconfirmed
    ]))
    for handle in handles:
        row = remote.get(handle) or {}
        local_activation = _parse_instant(checkpoints[handle].get("activated_at"))
        remote_activation = _parse_instant(row.get("activated_at"))
        checkpoints[handle]["activated_at"] = _iso(remote_activation or local_activation or now)
        if remote_activation is not None and remote_activation != local_activation:
            # Progress under a different activation does not establish coverage
            # of the durable interval. Resume from the durable progress alone.
            checkpoints[handle].pop("scanned_through", None)
        local_through = _parse_instant(checkpoints[handle].get("scanned_through"))
        remote_through = _parse_instant(row.get("scanned_through"))
        # The older of the two is the only safe resume point: whichever side
        # is behind still has an uncollected interval to re-walk.
        through = min([value for value in (local_through, remote_through) if value], default=None)
        if through is not None:
            checkpoints[handle]["scanned_through"] = _iso(through)
        # Reconciliation rotates by attempts, independently of successful
        # coverage. Restore that ordering too when the local cache is lost.
        local_attempt = _parse_instant(checkpoints[handle].get("last_scan_at"))
        remote_attempt = _parse_instant(row.get("last_scan_at"))
        if remote_attempt is not None and (local_attempt is None or remote_attempt > local_attempt):
            checkpoints[handle]["last_scan_at"] = _iso(remote_attempt)
            checkpoints[handle]["last_status"] = row.get("last_status")

    for handle in unconfirmed:
        if _parse_instant((remote.get(handle) or {}).get("activated_at")) is None:
            log.warning(
                "%s: activation is local-only this run (durable store unavailable); "
                "the boundary will be confirmed on the next successful run",
                handle,
            )
        else:
            log.info("post collection activation confirmed for %s at %s",
                     handle, checkpoints[handle]["activated_at"])
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
            # Video nodes still expose a JPEG cover; OCR that still.
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


# ------------------------------------------------------------------ scanning


class AccountResult(NamedTuple):
    handle: str
    discovered: int
    updated: int
    unchanged: int
    scanned: int
    complete: bool
    media_ids: list[str]


def _graphql_feed_posts(L: instaloader.Instaloader, handle: str,
                        user_id: str) -> Iterable[instaloader.Post]:
    """The logged-in 4.15.3 get_posts query, without its metadata lookup.

    A profile can show unrelated posts. Only yield posts whose author or accepted
    coauthor matches the stored ID; require at least one match to verify coverage.
    Keep raw pages intact so skipped entries cannot truncate upstream pagination.
    """
    if not L.context.is_logged_in:
        raise RuntimeError(f"{handle}: GraphQL post collection requires login")
    verified_account = False
    saw_entries = False

    def extract_page(response: dict[str, Any]) -> dict[str, Any]:
        nonlocal saw_entries
        # HTTP 200 can still contain an API refusal. Keep its message in an
        # Instaloader exception so the collector's cooldown classifier sees it.
        diagnostic = {key: response[key] for key in
                      ("errors", "message", "status", "feedback_title") if key in response}
        if response.get("errors") or response.get("status") == "fail":
            if any(isinstance(err, dict) and err.get("description") == "User lookup returned null"
                   for err in response.get("errors") or []):
                # The query addresses the handle, so a deleted, deactivated or
                # renamed account has nothing to look up. Skip it, not the run.
                raise ProfileNotExistsException(
                    f"{handle}: no Instagram account has this handle (deleted, deactivated or renamed)")
            raise ConnectionException(f"{handle}: GraphQL feed error: {json.dumps(diagnostic)}")
        data = response.get("data")
        page = data.get("xdt_api__v1__feed__user_timeline_graphql_connection") if isinstance(data, dict) else None
        if not isinstance(page, dict):
            raise ConnectionException(
                f"{handle}: malformed GraphQL feed: missing or null timeline data; {json.dumps(diagnostic)}")
        edges = page.get("edges")
        page_info = page.get("page_info")
        if (not isinstance(edges, list) or not isinstance(page_info, dict)
                or not isinstance(page_info.get("has_next_page"), bool)
                or (page_info["has_next_page"] and not page_info.get("end_cursor"))):
            raise RuntimeError(f"{handle}: malformed GraphQL feed page")
        for edge in edges:
            node = edge.get("node") if isinstance(edge, dict) else None
            if not isinstance(node, dict):
                raise RuntimeError(f"{handle}: malformed GraphQL feed node")
            owner = node.get("user")
            if not isinstance(owner, dict) or not owner.get("pk"):
                raise RuntimeError(
                    f"{handle}: GraphQL post {node.get('code')!r} has no verifiable author ID"
                )
        if not edges and not saw_entries and not page_info["has_next_page"]:
            # Nothing to verify and nothing to collect; coverage is not advanced.
            raise EmptyFeed(f"{handle}: empty GraphQL feed (no posts, or a private profile)")
        if not edges and (not verified_account or page_info["has_next_page"]):
            raise RuntimeError(f"{handle}: empty GraphQL feed cannot verify account identity/coverage")
        saw_entries = saw_entries or bool(edges)
        return page

    # Keep this aligned with Profile.get_posts in the pinned Instaloader version.
    # NodeIterator retains upstream pagination, transport, and rate control.
    nodes = instaloader.NodeIterator(
        context=L.context,
        query_hash=None,
        edge_extractor=extract_page,
        node_wrapper=lambda node: node,
        query_variables={
            "data": {
                "count": 12,
                "include_relationship_info": True,
                "latest_besties_reel_media": True,
                "latest_reel_media": True,
            },
            "username": handle,
        },
        query_referer=f"https://www.instagram.com/{handle}/",
        doc_id="7898261790222653",
    )
    for node in nodes:
        owner_id = node["user"]["pk"]
        # Invitations and ordinary tags do not establish profile membership.
        coauthors = node.get("coauthor_producers") or []
        is_coauthor = isinstance(coauthors, list) and any(
            isinstance(author, dict) and str(author.get("pk")) == user_id
            for author in coauthors
        )
        if str(owner_id) != user_id and not is_coauthor:
            log.warning(
                "%s: skipping GraphQL post %r by author ID %r; stored ID %s is "
                "neither author nor accepted coauthor",
                handle, node.get("code"), owner_id, user_id,
            )
            continue
        verified_account = True
        yield instaloader.Post.from_iphone_struct(L.context, node)
    if not verified_account:
        raise RuntimeError(
            f"{handle}: stored ID {user_id} is not an author and not an accepted coauthor "
            "of any returned post; cannot verify feed membership"
        )


def scan_account(
    L: instaloader.Instaloader,
    account: dict[str, Any],
    checkpoint: dict[str, Any],
    now: datetime,
    *,
    direct_feed: bool = False,
    backfill_since: datetime | None = None,
) -> AccountResult:
    """Walk one profile's feed back to its boundary and save what is new.

    Raw writes are made durable before the caller advances the checkpoint, so
    an interrupted scan keeps what it collected and re-walks the rest next run.
    The date boundary limits the walk; a fixed post count would repeatedly stop
    a busy account at the same newest-first prefix without ever catching up.
    """
    handle = account["handle"]
    # A maintenance backfill bypasses both activation and recent progress without
    # changing the stored activation used by normal incremental collection.
    boundary = backfill_since or scan_boundary(checkpoint, now)
    user_id = account.get("instagram_user_id")
    if not user_id:
        raise ValueError(f"{handle}: missing instagram_user_id; run resolve_ids.py first")
    if direct_feed:
        posts = _direct_feed_posts(L, handle, str(user_id))
    else:
        posts = _graphql_feed_posts(L, handle, str(user_id))

    records: list[dict[str, Any]] = []
    counts = {"new": 0, "updated": 0, "unchanged": 0}
    scanned = 0
    complete = False
    try:
        for number, post in enumerate(posts, start=1):
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
        else:
            complete = True
    except DirectFeedLimitReached as exc:
        log.warning("%s; retaining scan checkpoint", exc)
    finally:
        if direct_feed:
            posts.close()

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


def failed_downloads(handles: set[str]) -> dict[str, dict[str, Any]]:
    """Refresh expired/missing image URLs before retrying saved download errors."""
    failed = set()
    for path in POST_EXTRACTED_DIR.glob("*.json"):
        try:
            cached = _read_json(path)
        except (ValueError, OSError):
            continue
        if (isinstance(cached, dict) and cached.get("status") == "error"
                and (cached.get("result") or {}).get("stage") == "download"):
            failed.add(str(cached.get("media_id")))
    return {str(record["media_id"]): record for record in iter_local_posts(handles)
            if str(record["media_id"]) in failed and record.get("shortcode")}


def _sleep_between_accounts() -> None:
    time.sleep(random.uniform(*ACCOUNT_SLEEP_RANGE))


def main(handles: list[str] | None = None, *, direct_feed: bool = False,
         discovery: str | None = None, reconcile_accounts: int = 120,
         following_max_pages: int = 100) -> None:
    """Collect posts; direct-feed pilots require at most five explicit handles."""
    wanted = {handle.strip().lower() for handle in (handles or []) if handle.strip()}
    mode = discovery or POST_DISCOVERY_MODE
    backfill_since = _parse_instant(POST_BACKFILL_SINCE)
    if POST_BACKFILL_SINCE:
        if backfill_since is None:
            raise ValueError("PIPELINE_POST_BACKFILL_SINCE must be an ISO date or timestamp")
        if direct_feed:
            raise ValueError("Historical backfill cannot use the bounded --direct-feed pilot")
        mode = "profiles"
    if mode not in ("profiles", "following"):
        raise ValueError("PIPELINE_POST_DISCOVERY/--discovery must be profiles or following")
    if direct_feed and mode != "profiles":
        raise ValueError("--direct-feed cannot be combined with Following discovery")
    if reconcile_accounts < 1 or following_max_pages < 1:
        raise ValueError("Reconciliation count and Following page budget must be positive")
    if direct_feed and not 1 <= len(wanted) <= DIRECT_FEED_MAX_ACCOUNTS:
        raise ValueError(
            f"--direct-feed requires 1–{DIRECT_FEED_MAX_ACCOUNTS} named --handle accounts"
        )
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if backfill_since is not None:
        log.info("Historical sweep: accounts.json profiles, posts since %s inclusive; "
                 "remove PIPELINE_POST_BACKFILL_SINCE to restore incremental scans",
                 _iso(backfill_since))
    # First: with a pause in force nothing below is worth doing, and extraction
    # restores the archive for itself.
    instagram_cooldown.ensure_collection_allowed("posts")
    ensure_post_dirs()
    # The archive is what decides which posts are new, which still need
    # refreshing, and which are already paid for — so a machine that lost
    # `data/` gets it back from the durable mirror before any of that is judged.
    hydrate_local_posts(archive=ArchiveIndex())

    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        rate_controller=PacedRateController,
        max_connection_attempts=1,
        request_timeout=60,
        fatal_status_codes=[401, 403],
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
    paused: instagram_cooldown.Pause | None = None
    failures: list[str] = []
    # Set once failures run together; the rest of the work would only repeat them.
    stopped: str | None = None
    streak = 0
    try:
        # The fast path uses the saved roster: enumerating all followees on each
        # run would add another account-sized request sequence before discovery.
        accounts = load_accounts() if mode == "following" else _load_scrape_accounts(L)
        if handles:
            accounts = [account for account in accounts
                        if str(account.get("handle") or "").lower() in wanted]
            missing = wanted - {str(account.get("handle") or "").lower() for account in accounts}
            if missing:
                raise RuntimeError(
                    f"Not in the account roster: {', '.join(sorted(missing))}. "
                    "Check the exact Instagram handles in the configured account roster."
                )
            log.info("Pilot run limited to %d account(s)", len(accounts))
        # Activation is claimed for exactly the accounts this run will fetch, so
        # a pilot does not silently start the clock for the whole roster.
        checkpoints = resolve_checkpoints(
            [str(account.get("handle") or "") for account in accounts], now)
        fetched: set[str] = set()
        following_result = None
        if mode == "following":
            import following_feed

            try:
                following_result = following_feed.collect(
                    L, accounts, checkpoints, now, max_pages=following_max_pages)
                fetched.update(following_result["media_ids"])
                for key in ("scanned", "discovered", "updated", "unchanged"):
                    totals[key] += following_result[key]
            except (Exception, SystemExit) as exc:
                block = instagram_cooldown.classify(exc)
                if block is not None:
                    raise instagram_cooldown.stop(block, "posts", exc) from exc
                raise RuntimeError(f"Following discovery stopped: {exc}") from exc
            accounts = following_feed.select_reconciliation(
                accounts, checkpoints, reconcile_accounts)
            log.info("Following mode: reconciling %d profiles this run", len(accounts))

        for index, account in enumerate(accounts, start=1):
            handle = str(account.get("handle") or "")
            if not handle:
                totals["skipped"] += 1
                continue
            totals["accounts"] += 1
            checkpoint = checkpoints.setdefault(handle, {"activated_at": _iso(now)})
            if mode == "following":
                # Persist attempts as well as successes, so an unreadable club
                # rotates out of the next batch without claiming coverage.
                checkpoint["last_scan_at"] = _iso(now)
                checkpoint["last_status"] = "incomplete"
                write_local_checkpoints({handle: checkpoint})
            try:
                result = scan_account(L, account, checkpoint, now, direct_feed=direct_feed,
                                      backfill_since=backfill_since)
            except (ProfileNotExistsException, PrivateProfileNotFollowedException,
                    QueryReturnedNotFoundException, EmptyFeed) as exc:
                totals["skipped"] += 1
                log.warning("%s: skipped, no readable feed (%s)", handle, exc)
                streak += 1
                if streak >= MAX_CONSECUTIVE_FAILURES:
                    stopped = f"{streak} unreadable accounts in a row; last {handle}: {exc}"
                    break
                continue
            except (Exception, SystemExit) as exc:  # noqa: BLE001 - per-account isolation.
                # Pushback does not get better by asking more accounts: stop, and
                # keep every checkpoint so the interval is re-walked later.
                block = instagram_cooldown.classify(exc, lone_400=True)
                totals["errors"] += 1
                failure = f"{handle}: {type(exc).__name__}: {exc}"
                failures.append(failure)
                checkpoint.update(last_scan_at=_iso(now), last_status="error", last_error=failure)
                write_local_checkpoints({handle: checkpoint})
                if block is not None:
                    paused = instagram_cooldown.pause(block, "posts", f"{handle}: {exc}")
                    break
                log.warning("%s: post scan failed; continuing: %s", handle, exc, exc_info=True)
                streak += 1
                if streak >= MAX_CONSECUTIVE_FAILURES:
                    stopped = f"{streak} failed accounts in a row; last {failure}"
                    break
                if index < len(accounts):
                    _sleep_between_accounts()
                continue
            streak = 0

            totals["scanned"] += result.scanned
            totals["discovered"] += result.discovered
            totals["updated"] += result.updated
            totals["unchanged"] += result.unchanged
            if following_result is not None:
                # Compare only the interval actually traversed by Following;
                # older profile catch-up is not a feed omission.
                feed_ids = set(following_result["media_ids"])
                boundary = _parse_instant(following_result["boundary"])
                missed = []
                for media_id in sorted(set(result.media_ids) - feed_ids):
                    record = _read_json(post_path(handle, media_id))
                    published = _parse_instant(record.get("posted_at"))
                    if published is not None and boundary <= published <= now:
                        missed.append(media_id)
                log.info("Following comparison %s: %d profile posts absent from feed: %s",
                         handle, len(set(missed)), sorted(set(missed)))
            fetched.update(result.media_ids)
            if result.complete:
                # Only a completed scan whose raw writes landed may move the
                # checkpoint; anything else re-walks its interval next run.
                checkpoint["scanned_through"] = _iso(now)
            else:
                totals["incomplete"] += 1
            checkpoint["last_scan_at"] = _iso(now)
            checkpoint["last_status"] = "complete" if result.complete else "incomplete"
            checkpoint.pop("last_error", None)
            write_local_checkpoints({handle: checkpoint})
            log.info(
                "%s: %d in window, %d new, %d updated, %d unchanged%s",
                handle, result.scanned, result.discovered, result.updated,
                result.unchanged, "" if result.complete else " (incomplete)",
            )
            if index < len(accounts):
                _sleep_between_accounts()

        if paused is None and stopped is None and not direct_feed:
            # Posts outside the overlap that still back an upcoming event.
            # Anything already fetched by discovery this run is skipped.
            refresh = refresh_candidates(now) if backfill_since is None else {}
            refresh.update(failed_downloads({account["handle"] for account in accounts}))
            for media_id, record in sorted(refresh.items()):
                if media_id in fetched:
                    continue
                try:
                    refresh_post(L, record, now)
                except (Exception, SystemExit) as exc:  # noqa: BLE001
                    block = instagram_cooldown.classify(exc, lone_400=True)
                    totals["errors"] += 1
                    failure = f"refresh {media_id}: {type(exc).__name__}: {exc}"
                    failures.append(failure)
                    if block is not None:
                        paused = instagram_cooldown.pause(
                            block, "posts", f"refresh {media_id}: {exc}"
                        )
                        break
                    log.warning("post %s: refresh failed; continuing: %s", media_id, exc)
                    streak += 1
                    if streak >= MAX_CONSECUTIVE_FAILURES:
                        stopped = f"{streak} failures in a row; last {failure}"
                        break
                    _sleep_between_accounts()
                    continue
                streak = 0
                totals["refreshed"] += 1
                fetched.add(media_id)
                _sleep_between_accounts()

        write_local_checkpoints(checkpoints)
        _write_remote_checkpoints(checkpoints)
        log.info("Done: %s", totals)
        if paused is not None:
            raise instagram_cooldown.CollectionStopped(
                f"Instagram post collection stopped early — {paused.describe()}: "
                f"{paused.detail}. Coverage is incomplete for this run; checkpoints "
                "were retained so the uncollected interval is re-walked once "
                "collection resumes."
            )
        if totals["incomplete"]:
            raise RuntimeError(
                f"Direct-feed pilot left {totals['incomplete']} account(s) incomplete; "
                "checkpoints were retained. Rerun without --direct-feed to finish coverage."
            )
        if stopped is not None:
            raise RuntimeError(
                f"Instagram post collection stopped after {stopped}. Checkpoints were "
                "retained; check the session and network before rerunning."
            )
        if totals["errors"]:
            raise PartialCollection(
                f"Instagram post collection hit {totals['errors']} failure(s) and continued "
                f"past them; checkpoints for those accounts were retained. First: {failures[0]}"
            )
    except Exception as exc:
        # Pushback outside the per-account loops, such as on the follow list. A
        # CollectionStopped raised above is never classified again.
        block = instagram_cooldown.classify(exc)
        if block is None:
            raise
        raise instagram_cooldown.stop(block, "posts", exc) from exc
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
    # A failed read/claim at startup may have left a local-only boundary. Never
    # let this upsert replace an older durable activation, or publish progress
    # from a scan that did not cover the durable interval.
    claimed = _claim_remote_activation([
        {"handle": row["handle"], "activated_at": row["activated_at"]} for row in rows
    ])
    confirmed = []
    for row in rows:
        activation = _parse_instant((claimed.get(row["handle"]) or {}).get("activated_at"))
        if activation is not None and activation == _parse_instant(row["activated_at"]):
            confirmed.append(row)
        else:
            log.warning("%s: durable activation unconfirmed or different; retaining remote progress",
                        row["handle"])
    if not confirmed:
        return
    try:
        from db import upsert_batched

        upsert_batched("instagram_post_checkpoints", confirmed, on_conflict="handle")
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - local cache remains usable.
        log.warning("post checkpoints: remote write failed: %s", exc)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handle", action="append",
                        help="limit collection to this account (repeatable); for pilots")
    parser.add_argument("--direct-feed", action="store_true",
                        help="pilot v1 feed fetching: 1–5 named handles, at most 3 pages each; no refresh pass")
    parser.add_argument("--discovery", choices=("profiles", "following"),
                        help="discovery mode; default PIPELINE_POST_DISCOVERY or profiles")
    parser.add_argument("--reconcile-accounts", type=int, default=120,
                        help="Following mode: oldest-attempted profiles per run (default 120)")
    parser.add_argument("--following-max-pages", type=int, default=100,
                        help="Following page budget; exhaustion retains progress (default 100)")
    args = parser.parse_args()
    if args.direct_feed and not 1 <= len({h.strip().lower() for h in (args.handle or [])
                                         if h.strip()}) <= DIRECT_FEED_MAX_ACCOUNTS:
        parser.error("--direct-feed requires 1–5 named --handle accounts")
    main(args.handle, direct_feed=args.direct_feed, discovery=args.discovery,
         reconcile_accounts=args.reconcile_accounts, following_max_pages=args.following_max_pages)
