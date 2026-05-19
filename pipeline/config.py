"""Shared paths and config for the Instagram stories pipeline."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

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

# Instaloader needs to be logged in to fetch stories. Two supported modes:
#   1. IG_USERNAME + IG_PASSWORD env vars  (interactive 2FA prompt if needed)
#   2. A session file dropped here by `instaloader -l <user>` (preferred for cron)
IG_USERNAME = os.environ.get("IG_USERNAME")
IG_PASSWORD = os.environ.get("IG_PASSWORD")
SESSION_FILE = os.environ.get("IG_SESSION_FILE")  # absolute path, optional
GOOGLE_VISION_API_KEY = os.environ.get("GOOGLE_VISION_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Highlander Link is fully gated behind UCR SSO. The discovery script reuses a
# session cookie pasted out of a logged-in browser (DevTools → Application →
# Cookies). Cookies typically last 2–4 weeks before re-login is needed.
HIGHLANDER_LINK_COOKIE = os.environ.get("HIGHLANDER_LINK_COOKIE")


def load_accounts() -> list[dict[str, Any]]:
    with ACCOUNTS_FILE.open() as f:
        return json.load(f)["accounts"]


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
