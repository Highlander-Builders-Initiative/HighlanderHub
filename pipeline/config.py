"""Shared paths and config for the Instagram stories pipeline."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    with path.open(encoding="utf-8") as f:
        return json.load(f).get("accounts", [])


def load_curated_accounts() -> list[dict[str, Any]]:
    return _read_accounts(ACCOUNTS_FILE)


def load_followed_accounts_cache() -> list[dict[str, Any]]:
    if not FOLLOWED_ACCOUNTS_FILE.exists():
        return []
    return _read_accounts(FOLLOWED_ACCOUNTS_FILE)


def write_followed_accounts_cache(accounts: list[dict[str, Any]]) -> None:
    FOLLOWED_ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "account_source": "instagram_followed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "accounts": accounts,
    }
    tmp = FOLLOWED_ACCOUNTS_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(FOLLOWED_ACCOUNTS_FILE)


def _uses_followed_accounts() -> bool:
    return ACCOUNT_SOURCE in {"followed", "following", "followees"}


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

    if ACCOUNT_SOURCE in {"accounts_json", "accounts.json", "configured", "curated"}:
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
