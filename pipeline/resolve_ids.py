"""Fill missing Instagram user IDs in accounts.json.

Offline step after discover.py: given handles, resolve numeric instagram_user_id
the same way tools like CommentPicker do (Instagram web_profile_info), then write
IDs back into accounts.json so scrape.py can use cached IDs.

Usage:
    python resolve_ids.py
    python resolve_ids.py --dry-run
    python resolve_ids.py --force
    python resolve_ids.py --only acm_ucr,cyber_ucr
    python resolve_ids.py --strict
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Callable

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")
load_dotenv(Path(__file__).resolve().parent / ".env")

from config import ACCOUNTS_FILE  # noqa: E402

log = logging.getLogger("pipeline.resolve_ids")

WEB_PROFILE_URL = "https://i.instagram.com/api/v1/users/web_profile_info/"
IG_APP_ID = "936619743392459"
TIMEOUT_S = 20
JITTER_RANGE = (2.0, 5.0)
BACKOFF_S = 45.0
MAX_ATTEMPTS = 3

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.instagram.com",
    "Referer": "https://www.instagram.com/",
    "x-ig-app-id": IG_APP_ID,
}


class ResolveError(Exception):
    """Failed to resolve a single handle."""


def _jitter() -> None:
    time.sleep(random.uniform(*JITTER_RANGE))


def _normalize_handle(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip().lstrip("@").rstrip("/").lower()
    s = s.split("?", 1)[0].split("/", 1)[0]
    if not s:
        return None
    return s


def _needs_id(account: dict[str, Any], *, force: bool) -> bool:
    if force:
        return True
    return account.get("instagram_user_id") is None


def _parse_user_id(payload: dict[str, Any], handle: str) -> int:
    user = (payload.get("data") or {}).get("user") or {}
    username = str(user.get("username") or "").strip().lower()
    if username and username != handle.lower():
        raise ResolveError(
            f"username mismatch: requested {handle!r}, got {username!r}"
        )
    raw_id = user.get("id")
    if raw_id is None:
        raise ResolveError("response missing data.user.id")
    try:
        return int(raw_id)
    except (TypeError, ValueError) as e:
        raise ResolveError(f"invalid user id: {raw_id!r}") from e


def fetch_user_id(
    session: requests.Session,
    handle: str,
    *,
    sleep_fn: Callable[[], None] | None = None,
) -> int:
    """Resolve handle to numeric Instagram user id via web_profile_info."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = session.get(
                WEB_PROFILE_URL,
                params={"username": handle},
                timeout=TIMEOUT_S,
            )
        except (requests.ConnectionError, requests.Timeout) as e:
            last_error = e
            log.warning("%s: network error (%s), attempt %d/%d", handle, e, attempt, MAX_ATTEMPTS)
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_S if attempt > 1 else 5.0)
            continue

        if resp.status_code in (429, 401, 403):
            last_error = ResolveError(f"HTTP {resp.status_code}")
            log.warning(
                "%s: HTTP %d, backing off %ss (attempt %d/%d)",
                handle,
                resp.status_code,
                BACKOFF_S,
                attempt,
                MAX_ATTEMPTS,
            )
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_S)
            continue

        if resp.status_code == 404:
            raise ResolveError("profile not found (404)")

        if resp.status_code != 200:
            raise ResolveError(f"HTTP {resp.status_code}: {resp.text[:200]}")

        try:
            payload = resp.json()
        except ValueError as e:
            raise ResolveError("response was not JSON") from e

        user_id = _parse_user_id(payload, handle)
        if sleep_fn is not None:
            sleep_fn()
        return user_id

    raise ResolveError(f"gave up after {MAX_ATTEMPTS} attempts: {last_error}")


def load_accounts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return json.load(f).get("accounts", [])


def write_accounts(path: Path, accounts: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = {"accounts": accounts}
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def resolve_accounts(
    accounts: list[dict[str, Any]],
    *,
    session: requests.Session,
    force: bool = False,
    only: set[str] | None = None,
    dry_run: bool = False,
    jitter: bool = True,
    fetch_fn: Callable[[requests.Session, str], int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return (updated_accounts, stats).

    stats keys: scanned, skipped, filled, failed, unchanged
    """
    fetch = fetch_fn or (lambda s, h: fetch_user_id(s, h))
    stats = {"scanned": 0, "skipped": 0, "filled": 0, "failed": 0, "unchanged": 0}
    updated: list[dict[str, Any]] = []

    for account in accounts:
        entry = dict(account)
        handle = _normalize_handle(entry.get("handle"))
        if not handle:
            updated.append(entry)
            continue

        entry["handle"] = handle
        stats["scanned"] += 1

        if only is not None and handle not in only:
            stats["skipped"] += 1
            updated.append(entry)
            continue

        if not _needs_id(entry, force=force):
            stats["unchanged"] += 1
            updated.append(entry)
            continue

        try:
            user_id = fetch(session, handle)
        except Exception as e:  # noqa: BLE001 — per-account isolation
            stats["failed"] += 1
            log.error("%s: resolve failed: %s", handle, e)
            updated.append(entry)
            if jitter:
                _jitter()
            continue

        prev = entry.get("instagram_user_id")
        entry["instagram_user_id"] = user_id
        stats["filled"] += 1
        if prev is None:
            log.info("%s: set instagram_user_id=%s", handle, user_id)
        else:
            log.info("%s: updated instagram_user_id %s to %s", handle, prev, user_id)

        updated.append(entry)
        if jitter:
            _jitter()

    if dry_run:
        log.info("dry-run: not writing accounts.json (%s)", stats)
    return updated, stats


def _parse_only(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    handles = set()
    for part in raw.split(","):
        h = _normalize_handle(part)
        if h:
            handles.add(h)
    return handles or None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fill missing instagram_user_id values in accounts.json"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-resolve IDs even when instagram_user_id is already set",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve and log, but do not write accounts.json",
    )
    parser.add_argument(
        "--only",
        help="Comma-separated handles to resolve (default: all missing)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any targeted handle failed to resolve",
    )
    parser.add_argument(
        "--no-jitter",
        action="store_true",
        help="Skip sleep between requests (tests / local debugging only)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    accounts = load_accounts(ACCOUNTS_FILE)
    if not accounts:
        log.warning("No accounts found in %s", ACCOUNTS_FILE)
        return 0

    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    updated, stats = resolve_accounts(
        accounts,
        session=session,
        force=args.force,
        only=_parse_only(args.only),
        dry_run=args.dry_run,
        jitter=not args.no_jitter,
    )

    if not args.dry_run and stats["filled"] > 0:
        write_accounts(ACCOUNTS_FILE, updated)
        log.info("Wrote %s (%s)", ACCOUNTS_FILE, stats)
    else:
        log.info("Done (%s)", stats)

    if args.strict and stats["failed"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
