"""Shared paths and config for the Instagram stories pipeline."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from accounts import (
    load_followed_accounts_cache as read_followed_accounts_cache,
    read_accounts,
    uses_curated_accounts,
    uses_followed_accounts,
    write_followed_accounts_cache as write_accounts_cache,
)

ROOT = Path(__file__).resolve().parent
log = logging.getLogger("pipeline.config")

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - setup installs python-dotenv.
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
EXTRACTED_DIR = DATA_DIR / "extracted"
ACCOUNTS_FILE = ROOT / "accounts.json"
FOLLOWED_ACCOUNTS_FILE = DATA_DIR / "followed_accounts.json"
ACCOUNT_SOURCE = os.environ.get("PIPELINE_ACCOUNT_SOURCE", "followed").lower()

# How many days back `normalize` re-pushes story snapshots to Supabase. Raw
# stories are immutable once scraped and the on-disk archive only grows, so
# re-upserting the whole history every run is unbounded wasted writes. Stories
# older than this stay as-is in Supabase (they were written when fresh). Widen
# this or set it <= 0 to force a full re-sync — e.g. after editing accounts.json
# labels or changing the story row shape. Override with
# PIPELINE_STORIES_WINDOW_DAYS.
try:
    STORIES_WINDOW_DAYS = int(os.environ.get("PIPELINE_STORIES_WINDOW_DAYS", "30"))
except ValueError:
    STORIES_WINDOW_DAYS = 30

# Instaloader needs to be logged in to fetch stories. Two supported modes:
#   1. IG_USERNAME + IG_PASSWORD env vars  (interactive 2FA prompt if needed)
#   2. A session file dropped here by `instaloader -l <user>` (preferred for cron)
IG_USERNAME = os.environ.get("IG_USERNAME")
IG_PASSWORD = os.environ.get("IG_PASSWORD")
SESSION_FILE = os.environ.get("IG_SESSION_FILE")  # absolute path, optional
GOOGLE_VISION_API_KEY = os.environ.get("GOOGLE_VISION_API_KEY")
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION") or "global"

# Highlander Link is fully gated behind UCR SSO. The discovery script reuses a
# session cookie pasted out of a logged-in browser (DevTools → Application →
# Cookies). Cookies typically last 2–4 weeks before re-login is needed.
HIGHLANDER_LINK_COOKIE = os.environ.get("HIGHLANDER_LINK_COOKIE")


def _read_accounts(path: Path) -> list[dict[str, Any]]:
    return read_accounts(path)


def load_curated_accounts() -> list[dict[str, Any]]:
    return _read_accounts(ACCOUNTS_FILE)


def load_followed_accounts_cache() -> list[dict[str, Any]]:
    return read_followed_accounts_cache(FOLLOWED_ACCOUNTS_FILE)


def write_followed_accounts_cache(accounts: list[dict[str, Any]]) -> None:
    write_accounts_cache(FOLLOWED_ACCOUNTS_FILE, accounts)


def _uses_followed_accounts() -> bool:
    return uses_followed_accounts(ACCOUNT_SOURCE)


def load_accounts() -> list[dict[str, Any]]:
    if _uses_followed_accounts():
        accounts = load_followed_accounts_cache()
        if accounts:
            log.info(
                "Account source: followed-account cache (%d accounts) from %s",
                len(accounts),
                FOLLOWED_ACCOUNTS_FILE,
            )
            return accounts
        curated = load_curated_accounts()
        log.warning(
            "Account source requested followed accounts, but %s is missing or empty; "
            "falling back to accounts.json (%d accounts)",
            FOLLOWED_ACCOUNTS_FILE,
            len(curated),
        )
        return curated

    if uses_curated_accounts(ACCOUNT_SOURCE):
        accounts = load_curated_accounts()
        log.info("Account source: accounts.json (%d accounts)", len(accounts))
        return accounts

    raise RuntimeError(
        "Unsupported PIPELINE_ACCOUNT_SOURCE="
        f"{ACCOUNT_SOURCE!r}; expected 'followed' or 'accounts_json'."
    )


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
