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
)

from config import (
    IG_PASSWORD,
    IG_USERNAME,
    RAW_DIR,
    SESSION_FILE,
    ensure_dirs,
    load_accounts,
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


# Hardcoded User ID mapping to completely bypass Instagram GraphQL lookups for known accounts.
# These IDs are permanent and will never change, ensuring high speed and reliability.
KNOWN_USER_IDS = {
    "cyber_ucr": 38460809748,
    "acm_ucr": 10839758322,
    "ucrvsa": 241289265,
}


def _resolve_profile(L: instaloader.Instaloader, handle: str) -> instaloader.Profile:
    """Resolve a username to an instaloader Profile object using a hybrid approach.

    1. If the handle has a hardcoded ID, instantiate Profile directly using the ID (0 network requests).
    2. Fallback to Instagram search (TopSearchResults GET query) which is unaffected by GraphQL bugs.
    3. Final fallback to instaloader's default from_username (GraphQL).
    """
    normalized_handle = handle.lower()

    # 1. Use hardcoded static IDs (Workaround B)
    if normalized_handle in KNOWN_USER_IDS:
        userid = KNOWN_USER_IDS[normalized_handle]
        log.info("%s: Resolved handle using static KNOWN_USER_IDS mapping (ID: %s)", handle, userid)
        return instaloader.Profile(L.context, {"username": handle, "id": str(userid)})

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


def scrape_account(L: instaloader.Instaloader, handle: str) -> tuple[int, int]:
    """Fetch stories for one account. Returns (seen, new)."""
    profile = _resolve_profile(L, handle)
    seen = new = 0
    for story in L.get_stories(userids=[profile.userid]):
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
    accounts = load_accounts()

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

    totals = {"accounts": 0, "seen": 0, "new": 0, "errors": 0, "missing_profiles": 0}
    for acct in accounts:
        handle = acct["handle"]
        totals["accounts"] += 1
        try:
            seen, new = scrape_account(L, handle)
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
