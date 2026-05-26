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
from pathlib import Path
from typing import Any

import instaloader
from instaloader.exceptions import (
    ConnectionException,
    LoginRequiredException,
    ProfileNotExistsException,
    QueryReturnedBadRequestException,
)

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
        "story_cta_url": getattr(item, "story_cta_url", None),
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


def _resolve_profile(
    L: instaloader.Instaloader,
    handle: str,
    *,
    instagram_user_id: int | None = None,
) -> instaloader.Profile:
    """Resolve a username to an instaloader Profile object using a hybrid approach.

    1. If account metadata has instagram_user_id, instantiate Profile directly (0 network requests).
    2. Fallback to Instagram search (TopSearchResults GET query) which is unaffected by GraphQL bugs.
    3. Final fallback to instaloader's default from_username (GraphQL).
    """
    normalized_handle = handle.lower()

    if instagram_user_id is not None:
        log.info(
            "%s: Resolved handle using cached instagram_user_id (%s)",
            handle,
            instagram_user_id,
        )
        return instaloader.Profile(
            L.context, {"username": handle, "id": str(instagram_user_id)}
        )

    # 2. Fallback to Search GET request (completely unaffected by issue #2695)
    try:
        search_results = instaloader.TopSearchResults(L.context, handle)
        for profile in search_results.get_profiles():
            if profile.username.lower() == normalized_handle:
                log.info("%s: Resolved handle via search (ID: %s)", handle, profile.userid)
                return profile
    except Exception as e:
        log.warning("%s: Search resolution failed: %s. Falling back to default lookup.", handle, e)

    # 3. Final fallback to instaloader's default from_username
    return instaloader.Profile.from_username(L.context, handle)


def _uses_followed_accounts() -> bool:
    return ACCOUNT_SOURCE in {"followed", "following", "followees"}


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
    if not _uses_followed_accounts():
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


def scrape_account(L: instaloader.Instaloader, acct: dict[str, Any]) -> tuple[int, int]:
    """Fetch stories for one account. Returns (seen, new)."""
    handle = acct["handle"]
    raw_id = acct.get("instagram_user_id")
    instagram_user_id = int(raw_id) if raw_id is not None else None
    profile = _resolve_profile(L, handle, instagram_user_id=instagram_user_id)
    seen = new = 0

    stories = L.get_stories(userids=[profile.userid])
    for story in stories:
        for item in story.get_items():
            seen += 1
            payload = _serialize_item(item, handle)
            if _write_item(payload, handle):
                new += 1
    return seen, new


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
    _login(L)
    accounts = _load_scrape_accounts(L)

    totals = {"accounts": 0, "seen": 0, "new": 0, "errors": 0, "missing_profiles": 0}
    for acct in accounts:
        handle = acct["handle"]
        totals["accounts"] += 1
        try:
            seen, new = scrape_account(L, acct)
            totals["seen"] += seen
            totals["new"] += new
            log.info("%s: %d items, %d new", handle, seen, new)
        except LoginRequiredException:
            log.error("Login required (session expired). Re-auth and re-run.")
            raise
        except ConnectionException as e:
            totals["errors"] += 1
            log.warning("%s: connection error: %s", handle, e)
        except ProfileNotExistsException as e:
            totals["errors"] += 1
            totals["missing_profiles"] += 1
            log.warning(
                "%s: profile lookup failed: %s. If this affects every account, "
                "Instagram is likely hiding profiles behind an expired, challenged, "
                "or rate-limited session.",
                handle,
                e,
                exc_info=True,
            )
        except Exception as e:  # noqa: BLE001 — keep run alive across per-account failures
            totals["errors"] += 1
            log.warning("%s: %s: %s", handle, type(e).__name__, e, exc_info=True)
        # Polite jitter between accounts. IG aggressively rate-limits scraping.
        time.sleep(random.uniform(2.0, 5.0))

    log.info("Done: %s", totals)
    if totals["errors"]:
        if (
            totals["missing_profiles"] == totals["accounts"]
            and totals["seen"] == 0
            and totals["accounts"] > 0
        ):
            raise RuntimeError(
                "Instagram session appears invalid, challenged, or rate-limited: "
                f"all {totals['accounts']} configured profiles returned "
                "ProfileNotExistsException. Refresh IG_SESSION_FILE and verify the "
                "scraper account can view these profiles before re-running."
            )
        raise RuntimeError(
            f"Instagram scrape failed for {totals['errors']} account(s); "
            "check the logs for expired sessions, auth challenges, or rate limits."
        )


if __name__ == "__main__":
    main()
