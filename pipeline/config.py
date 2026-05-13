"""Shared paths and config for the Instagram stories pipeline."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
ACCOUNTS_FILE = ROOT / "accounts.json"

# Instaloader needs to be logged in to fetch stories. Two supported modes:
#   1. IG_USERNAME + IG_PASSWORD env vars  (interactive 2FA prompt if needed)
#   2. A session file dropped here by `instaloader -l <user>` (preferred for cron)
IG_USERNAME = os.environ.get("IG_USERNAME")
IG_PASSWORD = os.environ.get("IG_PASSWORD")
SESSION_FILE = os.environ.get("IG_SESSION_FILE")  # absolute path, optional


def load_accounts() -> list[dict[str, Any]]:
    with ACCOUNTS_FILE.open() as f:
        return json.load(f)["accounts"]


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
