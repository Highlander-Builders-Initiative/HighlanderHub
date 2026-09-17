"""Shared paths and config for the event ingestion pipeline."""
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
POSTS_DIR = DATA_DIR / "posts"
POST_EXTRACTED_DIR = DATA_DIR / "post_extractions"
POST_CHECKPOINTS_FILE = DATA_DIR / "post_checkpoints.json"
FOLLOWING_CHECKPOINT_FILE = DATA_DIR / "following_checkpoint.json"
# Keep profile collection as the default until Following recall is measured.
POST_DISCOVERY_MODE = os.environ.get("PIPELINE_POST_DISCOVERY", "profiles").lower()
ACCOUNTS_FILE = ROOT / "accounts.json"
FOLLOWED_ACCOUNTS_FILE = DATA_DIR / "followed_accounts.json"
ACCOUNT_SOURCE = os.environ.get("PIPELINE_ACCOUNT_SOURCE", "followed").lower()

# Authenticate using credentials or a saved Instaloader session file.
IG_USERNAME = os.environ.get("IG_USERNAME")
IG_PASSWORD = os.environ.get("IG_PASSWORD")
SESSION_FILE = os.environ.get("IG_SESSION_FILE")  # absolute path, optional
GOOGLE_VISION_API_KEY = os.environ.get("GOOGLE_VISION_API_KEY")
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION") or "global"


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


# How far back a post scan re-walks the profile feed before trusting its
# checkpoint. Instagram orders the feed by publication time, so a 7-day overlap
# absorbs a late edit, a clock skew, and a run that was interrupted partway.
try:
    POST_OVERLAP_DAYS = int(os.environ.get("PIPELINE_POST_OVERLAP_DAYS", "7"))
except ValueError:
    POST_OVERLAP_DAYS = 7

# When Instagram challenges or throttles collection, requests stop
# and stay paused this long (see instagram_cooldown.py): asking again straight
# after pushback is what escalates a throttle into a checkpoint. Override with
# PIPELINE_INSTAGRAM_COOLDOWN_HOURS.
INSTAGRAM_COOLDOWN_FILE = DATA_DIR / "instagram_cooldown.json"
try:
    INSTAGRAM_COOLDOWN_HOURS = float(
        os.environ.get("PIPELINE_INSTAGRAM_COOLDOWN_HOURS", "24")
    )
except ValueError:
    INSTAGRAM_COOLDOWN_HOURS = 24.0


def ensure_post_dirs() -> None:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    POST_EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)


def load_account_meta() -> dict[str, dict[str, Any]]:
    return {account["handle"]: account for account in load_accounts()}
