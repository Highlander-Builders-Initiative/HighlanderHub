"""Account-source helpers for the Instagram pipeline."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FOLLOWED_ACCOUNT_SOURCES = {"followed", "following", "followees"}
CURATED_ACCOUNT_SOURCES = {"accounts_json", "accounts.json", "configured", "curated"}


def uses_followed_accounts(source: str) -> bool:
    return source.lower() in FOLLOWED_ACCOUNT_SOURCES


def uses_curated_accounts(source: str) -> bool:
    return source.lower() in CURATED_ACCOUNT_SOURCES


def read_accounts(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return json.load(f).get("accounts", [])


def load_followed_accounts_cache(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return read_accounts(path)


def write_followed_accounts_cache(path: Path, accounts: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "account_source": "instagram_followed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "accounts": accounts,
    }
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(path)
