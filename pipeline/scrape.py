"""Fetch Instagram stories for the configured accounts.

Writes one JSON file per story item to data/raw/<handle>/<item_id>.json.
Idempotent: existing files are skipped, so re-runs are cheap and the on-disk
set is the union of everything we've ever seen (useful — IG stories expire
in 24h, so the raw archive is the only durable record).
"""
from __future__ import annotations

import json
import logging
import random
import time
from typing import Any, Iterator, NamedTuple
from urllib.parse import parse_qs, urlsplit

import instaloader
from instaloader.exceptions import (
    ConnectionException,
    IPhoneSupportDisabledException,
    LoginRequiredException,
    QueryReturnedBadRequestException,
)

from accounts import uses_followed_accounts
from config import (
    ACCOUNT_SOURCE,
    FOLLOWED_ACCOUNTS_FILE,
    IG_PASSWORD,
    IG_USERNAME,
    RAW_DIR,
    SESSION_FILE,
    ensure_dirs,
    load_curated_accounts,
    load_followed_accounts_cache,
    write_followed_accounts_cache,
)

log = logging.getLogger("pipeline.scrape")

# How many accounts go into one reels_media request. Matches instaloader's own
# internal chunk size, so the request looks like what Instagram already gets
# from a large installed base. This is not a tuning knob: Instagram's cap on
# `reel_ids` is undocumented, and raising it is unvalidated. If Instagram ever
# rejects requests this large, the split-retry below finds the working size and
# logs it — lower this constant to match rather than guessing upward.
STORY_CHUNK_SIZE = 50

# Jitter between chunks. One chunk covers 50 accounts, so a full run is ~17
# requests and the sleeps can be far more generous than the old per-account 2–5s
# while still finishing in minutes.
CHUNK_SLEEP_RANGE = (5.0, 15.0)


class InstagramStoriesBadRequest(RuntimeError):
    """Fatal Instagram stories API failure that should stop the run."""


# Response headers Instagram sets when it throttles or challenges a request.
# A plain 400 "invalid request" (malformed/expired query), a 429 rate limit, and
# a checkpoint/challenge all surface to instaloader as similar-looking errors —
# the distinguishing signal lives in these headers and the raw body, both of
# which the exception message discards.
_DIAGNOSTIC_HEADERS = (
    "retry-after",
    "x-ratelimit-remaining",
    "x-fb-rlafr",
    "www-authenticate",
    "x-ig-set-www-claim",
    "content-type",
)


def _log_http_errors(resp: Any, *args: Any, **kwargs: Any) -> Any:
    """requests response hook: dump the real status code, the headers that
    reveal throttling/challenge state, and the response body for any 4xx/5xx
    Instagram returns. This makes a 400 diagnosable (malformed query vs. rate
    limit vs. checkpoint) instead of guessing from the generic 'bad request'.
    """
    if resp.status_code < 400:
        return resp
    headers = {
        k: v for k, v in resp.headers.items() if k.lower() in _DIAGNOSTIC_HEADERS
    }
    body = resp.text[:1000]
    truncated = "… (truncated)" if len(resp.text) > 1000 else ""
    log.warning(
        "Instagram HTTP %s %s on %s\n  diagnostic headers: %s\n  body: %s%s",
        resp.status_code,
        resp.reason,
        resp.url,
        headers,
        body,
        truncated,
    )
    return resp


def _attach_http_error_logger(L: instaloader.Instaloader) -> None:
    session = getattr(getattr(L, "context", None), "_session", None)
    hooks = getattr(session, "hooks", None)
    if not isinstance(hooks, dict):
        return

    response_hooks = hooks.setdefault("response", [])
    if hasattr(response_hooks, "append") and _log_http_errors not in response_hooks:
        response_hooks.append(_log_http_errors)


def _login(L: instaloader.Instaloader) -> None:
    if SESSION_FILE:
        # Session file produced by `instaloader -l <user>`; safer for unattended runs.
        L.load_session_from_file(IG_USERNAME or "", SESSION_FILE)
        log.info("Loaded session from %s", SESSION_FILE)
        # Bypassing strict L.test_login() check because Instagram's test query hash
        # is heavily rate-limited on CI environments (e.g. GitHub Actions).
        # Any actual session expiration will be caught during the scraping requests.
        return
    if not IG_USERNAME or not IG_PASSWORD:
        raise SystemExit(
            "Instagram credentials required. Set IG_USERNAME + IG_PASSWORD, "
            "or IG_SESSION_FILE pointing to a session created by "
            "`instaloader -l <user>`."
        )
    L.login(IG_USERNAME, IG_PASSWORD)
    log.info("Logged in as %s", IG_USERNAME)


def _current_sessionid(L: instaloader.Instaloader) -> str | None:
    """Return the live `sessionid` cookie value from the in-memory jar, if any."""
    session = getattr(getattr(L, "context", None), "_session", None)
    cookies = getattr(session, "cookies", None)
    if cookies is None:
        return None
    for cookie in cookies:
        if (
            cookie.name == "sessionid"
            and str(getattr(cookie, "domain", "")).endswith("instagram.com")
            and cookie.value
        ):
            return cookie.value
    return None


def _persist_rotated_session(L: instaloader.Instaloader) -> None:
    """Write the (possibly rotated) session cookies back to SESSION_FILE.

    Instagram rotates `sessionid` via Set-Cookie as the session is used, but we
    only ever loaded a snapshot at startup and never saved the rotated jar back.
    Every run therefore replayed an aging snapshot until it went stale — which
    happens within a day or two when the same account is also live in a browser
    that rotates the shared cookie out from under the on-disk copy. Persisting the
    rotated jar after each run keeps the file current so the session survives.

    Guards (mirrors import_safari_session.py so a dead run can't clobber a good
    file):
      * Only writes in session-file mode (IG_SESSION_FILE configured).
      * Refuses to overwrite when the jar has no `sessionid` (logged-out/expired).
      * Never raises — persistence must not mask the scrape's own result.
    """
    if not SESSION_FILE:
        return
    try:
        sessionid = _current_sessionid(L)
        if not sessionid:
            log.warning(
                "Not saving session back to %s: no live sessionid cookie "
                "(session looks logged out/expired). Left the file untouched.",
                SESSION_FILE,
            )
            return
        L.save_session_to_file(SESSION_FILE)
        log.info("Saved rotated session back to %s", SESSION_FILE)
    except Exception as e:  # noqa: BLE001 — persistence must never break the run
        log.warning("Could not persist rotated session to %s: %s", SESSION_FILE, e)


_LINK_SHIM_HOSTS = {"l.instagram.com", "lm.instagram.com"}


def _unwrap_link_shim(url: Any) -> str | None:
    """Return the real destination behind an `l.instagram.com/?u=<target>` wrapper.

    Instagram rewrites outbound story links through that shim, and the wrapper
    carries a signed `e` parameter that expires. Storing the wrapper would put a
    link that stops working into every rsvp_url.
    """
    if not isinstance(url, str) or not url.strip():
        return None
    url = url.strip()
    parts = urlsplit(url)
    if parts.netloc.lower() not in _LINK_SHIM_HOSTS:
        return url
    target = parse_qs(parts.query).get("u") or []
    return target[0] if target and target[0] else url


def _dict_entries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _story_cta_url(item: Any) -> str | None:
    """Return the link a club attached to a story item, or None.

    `StoryItem` exposes no property for this — the link lives only in the iphone
    struct, which `Story.get_items()` has already stitched onto the item, so
    reading it costs no extra request. Instagram uses two shapes: the link
    sticker that replaced swipe-up in 2021, and the legacy swipe-up payload.
    """
    try:
        struct = item._iphone_struct
    except (IPhoneSupportDisabledException, KeyError):
        return None
    if not isinstance(struct, dict):
        return None

    for sticker in _dict_entries(struct.get("story_link_stickers")):
        link = sticker.get("story_link")
        url = _unwrap_link_shim(link.get("url")) if isinstance(link, dict) else None
        if url:
            return url

    for cta in _dict_entries(struct.get("story_cta")):
        for link in _dict_entries(cta.get("links")):
            url = _unwrap_link_shim(link.get("webUri"))
            if url:
                return url

    return None


def _serialize_item(item: Any, handle: str) -> dict[str, Any]:
    """Pull the fields we care about off an instaloader StoryItem."""
    return {
        "id": str(item.mediaid),
        "handle": handle,
        "owner_userid": getattr(item.owner_profile, "userid", None),
        "owner_username": getattr(item.owner_profile, "username", handle),
        "typename": item.typename,
        "is_video": item.is_video,
        "posted_at": item.date_utc.isoformat() + "Z",
        "expires_at": (
            item.expiring_utc.isoformat() + "Z" if item.expiring_utc else None
        ),
        "image_url": item.url,
        "video_url": item.video_url if item.is_video else None,
        "caption": item.caption,
        "caption_mentions": list(getattr(item, "caption_mentions", []) or []),
        "story_cta_url": _story_cta_url(item),
        # Best-effort link to view in browser (only works while story is live).
        "permalink": f"https://www.instagram.com/stories/{handle}/{item.mediaid}/",
    }


def _write_item(item_dict: dict[str, Any], handle: str) -> bool:
    """Write the item to raw/. Returns True if newly written, False if skipped."""
    out_dir = RAW_DIR / handle
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{item_dict['id']}.json"
    if path.exists():
        return False
    with path.open("w") as f:
        json.dump(item_dict, f, indent=2, sort_keys=True)
    return True


def _chunks(
    accounts: list[dict[str, Any]], size: int
) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(accounts), size):
        yield accounts[start : start + size]


def _index_by_userid(
    accounts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], list[dict[str, Any]]]:
    """Split accounts into what we can batch and what we can't.

    Returns `(batchable, by_userid, skipped)`. A batched reels_media response
    identifies each story only by owner id, so `by_userid` is how a story gets
    attributed back to a handle. `skipped` holds accounts with no
    `instagram_user_id` — batching addresses accounts by id, so those can't be
    asked about at all.
    """
    batchable: list[dict[str, Any]] = []
    by_userid: dict[int, dict[str, Any]] = {}
    skipped: list[dict[str, Any]] = []

    for acct in accounts:
        try:
            userid = int(acct["instagram_user_id"])
        except (KeyError, TypeError, ValueError):
            skipped.append(acct)
            continue

        claimed = by_userid.get(userid)
        if claimed is not None:
            log.warning(
                "%s and %s both claim instagram_user_id %s; keeping %s. Stories for "
                "an ambiguous id would land in whichever directory won the race — "
                "fix the duplicate in accounts.json.",
                claimed["handle"],
                acct.get("handle"),
                userid,
                claimed["handle"],
            )
            continue

        by_userid[userid] = acct
        batchable.append(acct)

    return batchable, by_userid, skipped


def _profile_username(profile: instaloader.Profile) -> str:
    return str(getattr(profile, "username", "") or "").strip()


def _account_from_followed_profile(
    profile: instaloader.Profile,
    curated_by_handle: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    handle = _profile_username(profile)
    existing = curated_by_handle.get(handle.lower(), {})
    account = dict(existing)
    account["handle"] = handle

    if not account.get("label"):
        account["label"] = str(getattr(profile, "full_name", "") or handle)

    user_id = getattr(profile, "userid", None)
    if user_id is not None:
        try:
            account["instagram_user_id"] = int(user_id)
        except (TypeError, ValueError):
            log.warning("%s: followed profile had invalid userid: %r", handle, user_id)

    account["account_source"] = "instagram_followed"
    return account, bool(existing)


def _load_followed_accounts(
    L: instaloader.Instaloader,
    curated_accounts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    username = IG_USERNAME or str(getattr(L.context, "username", "") or "")
    if not username:
        raise RuntimeError(
            "IG_USERNAME is required when PIPELINE_ACCOUNT_SOURCE=followed so "
            "the scraper can enumerate the logged-in account's follow list."
        )

    viewer = instaloader.Profile.from_username(L.context, username)
    curated_by_handle = {
        str(account.get("handle", "")).lower(): account
        for account in curated_accounts
        if account.get("handle")
    }
    by_handle: dict[str, dict[str, Any]] = {}
    matched_curated = 0

    for profile in viewer.get_followees():
        handle = _profile_username(profile)
        if not handle:
            continue
        account, matched = _account_from_followed_profile(profile, curated_by_handle)
        by_handle[handle.lower()] = account
        if matched:
            matched_curated += 1

    accounts = sorted(by_handle.values(), key=lambda account: account["handle"].lower())
    return accounts, matched_curated


def _load_scrape_accounts(L: instaloader.Instaloader) -> list[dict[str, Any]]:
    curated_accounts = load_curated_accounts()
    if not uses_followed_accounts(ACCOUNT_SOURCE):
        log.info("Account source: accounts.json (%d accounts)", len(curated_accounts))
        return curated_accounts

    try:
        accounts, matched_curated = _load_followed_accounts(L, curated_accounts)
    except (QueryReturnedBadRequestException, ConnectionException) as e:
        log.warning(
            "Could not fetch Instagram follow list (%s). Imported/Safari sessions "
            "often fail this GraphQL call; using follow cache or accounts.json.",
            e,
        )
        cached = load_followed_accounts_cache()
        if cached:
            log.info(
                "Account source: followed-account cache (%d accounts) from %s",
                len(cached),
                FOLLOWED_ACCOUNTS_FILE,
            )
            return cached
        log.warning(
            "No followed-account cache; falling back to accounts.json (%d accounts)",
            len(curated_accounts),
        )
        return curated_accounts

    if not accounts:
        raise RuntimeError(
            "Instagram returned zero followed accounts; refusing to replace the "
            "runtime account cache. Check the scraper account's follow list and "
            "session health."
        )
    write_followed_accounts_cache(accounts)
    log.info(
        "Account source: followed accounts (%d accounts; %d matched accounts.json "
        "metadata; cache=%s)",
        len(accounts),
        matched_curated,
        FOLLOWED_ACCOUNTS_FILE,
    )
    return accounts


class StoryFetch(NamedTuple):
    """What one chunk's worth of requests produced, after any split-retry."""

    stories: list[Any]
    # Sizes Instagram accepted. Empty means every request in this subtree failed.
    accepted_sizes: list[int]
    # Userids Instagram rejected when asked about on their own.
    rejected_userids: list[int]


def _fetch_stories(L: instaloader.Instaloader, userids: list[int]) -> StoryFetch:
    """Fetch stories for `userids`, halving and retrying whatever gets rejected.

    Recursing down to size 1 covers two different failures with one mechanism: a
    poison userid (deleted, banned, mistyped) is isolated in ~12 requests instead
    of costing 50 accounts their run, and a server-side cap below
    STORY_CHUNK_SIZE degrades to whatever size Instagram does accept. Which one
    happened is reported by the caller from the counts returned here.
    """
    try:
        # get_stories() is a generator — the request only fires on iteration, so
        # the failure would escape this handler if we didn't materialize here.
        stories = list(L.get_stories(userids=list(userids)))
    except QueryReturnedBadRequestException as e:
        if len(userids) == 1:
            log.warning("Instagram rejected userid %s on its own: %s", userids[0], e)
            return StoryFetch([], [], list(userids))

        half = len(userids) // 2
        log.warning(
            "Instagram rejected a %d-account story request (%s); retrying as %d + %d",
            len(userids),
            e,
            half,
            len(userids) - half,
        )
        left = _fetch_stories(L, userids[:half])
        right = _fetch_stories(L, userids[half:])
        return StoryFetch(
            left.stories + right.stories,
            left.accepted_sizes + right.accepted_sizes,
            left.rejected_userids + right.rejected_userids,
        )

    return StoryFetch(stories, [len(userids)], [])


class ChunkResult(NamedTuple):
    seen: int
    new: int
    posting: int
    accepted_sizes: list[int]
    rejected_userids: list[int]


def scrape_chunk(
    L: instaloader.Instaloader,
    chunk: list[dict[str, Any]],
    by_userid: dict[int, dict[str, Any]],
) -> ChunkResult:
    """Fetch stories for a chunk of accounts in one request.

    reels_media only returns entries for accounts with a live story, so a
    50-account chunk typically yields two or three of them.
    """
    userids = [int(acct["instagram_user_id"]) for acct in chunk]
    fetch = _fetch_stories(L, userids)

    if not fetch.accepted_sizes and len(userids) > 1:
        raise InstagramStoriesBadRequest(
            f"Instagram rejected all {len(userids)} accounts in this chunk, including "
            "every one of them asked about individually. Only a dead, challenged, or "
            "rate-limited session fails every account at once — a bad account would "
            "have left the rest of the chunk working. Stopping the Instagram scrape "
            "now; refresh IG_SESSION_FILE before re-running."
        )

    seen = new = posting = 0
    for story in fetch.stories:
        acct = by_userid.get(story.owner_id)
        if acct is None:
            log.warning(
                "Ignoring stories from owner id %s, which this chunk never asked about",
                story.owner_id,
            )
            continue

        handle = acct["handle"]
        _warn_on_handle_rename(story, handle)

        try:
            items = list(story.get_items())
        except KeyError:
            # The iphone reels response omitted this owner. Rare once the GraphQL
            # response has already named them, but it means no readable items.
            log.info("%s: reels response carried no items for this account", handle)
            continue

        story_seen = story_new = 0
        for item in items:
            story_seen += 1
            if _write_item(_serialize_item(item, handle), handle):
                story_new += 1

        if story_seen:
            posting += 1
            log.info("%s: %d items, %d new", handle, story_seen, story_new)
        seen += story_seen
        new += story_new

    return ChunkResult(seen, new, posting, fetch.accepted_sizes, fetch.rejected_userids)


def _warn_on_handle_rename(story: Any, handle: str) -> None:
    """Flag a club that renamed itself.

    The raw directory and the permalink both come from the handle in the
    accounts list, never from `owner_username` — trusting Instagram's current
    name would start a second orphan directory and orphan the archive. But the
    permalink only resolves under the current name, so a rename needs saying out
    loud, and nothing detects it today.
    """
    reported = str(getattr(story, "owner_username", "") or "").strip()
    if reported and reported.lower() != handle.lower():
        log.warning(
            "%s now posts as @%s. Still writing to data/raw/%s so the archive stays "
            "joinable, but permalinks will be wrong until accounts.json is updated.",
            handle,
            reported,
            handle,
        )


def _log_rejection_diagnosis(
    *,
    rejected_handles: list[str],
    oversize_rejections: int,
    chunk_count: int,
    accepted_sizes: list[int],
) -> None:
    """Say which of the two split-retry failures the run actually saw.

    A bad account and a server-side chunk cap both start as a rejected
    full-size request, and the fix for each is different, so the run has to
    name which one it was rather than leaving it to be inferred from the logs.
    """
    if rejected_handles:
        log.error(
            "Instagram rejected %d account(s) asked about individually: %s. That is a "
            "bad userid — deleted, banned, or mistyped — not a size limit, since the "
            "rest of the chunk went through. Prune or re-resolve these entries in "
            "accounts.json.",
            len(rejected_handles),
            ", ".join(sorted(rejected_handles)),
        )
        return

    largest_accepted = max(accepted_sizes, default=0)
    if (
        chunk_count
        and oversize_rejections == chunk_count
        and 0 < largest_accepted < STORY_CHUNK_SIZE
    ):
        log.error(
            "Instagram rejected every full-size request but accepted %d accounts at "
            "once, and no individual account was at fault. That is a server-side cap "
            "on reel_ids: lower STORY_CHUNK_SIZE from %d to %d.",
            largest_accepted,
            STORY_CHUNK_SIZE,
            largest_accepted,
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ensure_dirs()

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
    # Register after _login: load_session_from_file replaces L.context._session,
    # which would drop a hook attached earlier.
    _attach_http_error_logger(L)
    try:
        accounts = _load_scrape_accounts(L)
        batchable, by_userid, skipped = _index_by_userid(accounts)
        if skipped:
            log.warning(
                "Skipping %d account(s) with no instagram_user_id: %s. Batched story "
                "fetch addresses accounts by id, so these are invisible to the run — "
                "run `python resolve_ids.py` to fill them in.",
                len(skipped),
                ", ".join(
                    sorted(str(acct.get("handle") or "<no handle>") for acct in skipped)
                ),
            )

        chunks = list(_chunks(batchable, STORY_CHUNK_SIZE))
        totals = {
            "accounts": len(batchable),
            "chunks": len(chunks),
            "posting": 0,
            "seen": 0,
            "new": 0,
            "errors": 0,
            "no_userid": len(skipped),
            "rejected_accounts": 0,
        }
        accepted_sizes: list[int] = []
        rejected_handles: list[str] = []
        oversize_rejections = 0

        for index, chunk in enumerate(chunks, start=1):
            try:
                result = scrape_chunk(L, chunk, by_userid)
            except LoginRequiredException:
                log.error("Login required (session expired). Re-auth and re-run.")
                raise
            except ConnectionException as e:
                totals["errors"] += 1
                log.warning("chunk %d/%d: connection error: %s", index, len(chunks), e)
            except InstagramStoriesBadRequest as e:
                totals["errors"] += 1
                log.error("%s", e)
                raise RuntimeError(str(e)) from None
            except Exception as e:  # noqa: BLE001 — keep the run alive across chunks
                totals["errors"] += 1
                log.warning(
                    "chunk %d/%d: %s: %s",
                    index,
                    len(chunks),
                    type(e).__name__,
                    e,
                    exc_info=True,
                )
            else:
                totals["seen"] += result.seen
                totals["new"] += result.new
                totals["posting"] += result.posting
                accepted_sizes.extend(result.accepted_sizes)
                # Any accepted sub-request is strictly smaller than the chunk, so
                # the chunk's own size showing up is exactly "the full-size
                # request went through".
                if len(chunk) not in result.accepted_sizes:
                    oversize_rejections += 1
                rejected_handles.extend(
                    by_userid[userid]["handle"] for userid in result.rejected_userids
                )
                log.info(
                    "chunk %d/%d: %d accounts, %d posting, %d items, %d new",
                    index,
                    len(chunks),
                    len(chunk),
                    result.posting,
                    result.seen,
                    result.new,
                )

            if index < len(chunks):
                time.sleep(random.uniform(*CHUNK_SLEEP_RANGE))

        # A rejected account no longer stops the run, but it still has to fail it:
        # nothing else would prompt anyone to prune the accounts.json entry.
        totals["rejected_accounts"] = len(rejected_handles)
        totals["errors"] += len(rejected_handles)
        _log_rejection_diagnosis(
            rejected_handles=rejected_handles,
            oversize_rejections=oversize_rejections,
            chunk_count=len(chunks),
            accepted_sizes=accepted_sizes,
        )

        log.info("Done: %s", totals)
        if totals["errors"]:
            raise RuntimeError(
                f"Instagram scrape hit {totals['errors']} failure(s); check the logs "
                "for rejected accounts, expired sessions, auth challenges, or rate "
                "limits."
            )
    finally:
        # Persist whatever the jar rotated to during this run, even when we exit by
        # raising (e.g. one flaky account). Guarded so a logged-out jar can't clobber
        # a still-good session file.
        _persist_rotated_session(L)


if __name__ == "__main__":
    main()
