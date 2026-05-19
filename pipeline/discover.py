"""Discover UCR club Instagram handles from Highlander Link.

Reads UCR's Engage instance (highlanderlink.ucr.edu) for student-org records,
extracts the Instagram handle off each org's profile, and merges new handles
into pipeline/accounts.json without clobbering hand-curated entries.

Usage:
    # HIGHLANDER_LINK_COOKIE in .env.local is loaded automatically.
    python discover.py

The pipeline:
    1. Paginate /api/discovery/search/organizations  → (Id, Name, Categories)
    2. For each active+public org:
         GET /api/discovery/organization/<Id>  → socialMedia.InstagramUrl
       Fall back to regex over description HTML if the structured field is empty.
    3. Merge {handle, label, category} into accounts.json.
       Hand-curated entries always win on handle conflict.
       Re-runs with no upstream changes produce a zero-line diff.
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load .env.local (where HIGHLANDER_LINK_COOKIE lives) BEFORE importing config,
# since config reads os.environ at module-import time.
load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

from config import ACCOUNTS_FILE, HIGHLANDER_LINK_COOKIE  # noqa: E402

log = logging.getLogger("pipeline.discover")

BASE_URL = "https://highlanderlink.ucr.edu"
SEARCH_PATH = "/api/discovery/search/organizations"
DETAIL_PATH = "/api/discovery/organization"  # /api/discovery/organization/<numeric_id>
PAGE_SIZE = 100
TIMEOUT_S = 15
JITTER_RANGE = (1.0, 3.0)
BACKOFF_S = 30.0
NETWORK_RETRY_S = 5.0
# Abort if more than this fraction of detail fetches fail with parse errors.
# Strong signal the API contract has shifted under us.
MAX_PARSE_FAIL_RATIO = 0.10

IG_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?",
    re.IGNORECASE,
)


def _jitter() -> None:
    time.sleep(random.uniform(*JITTER_RANGE))


def _session() -> requests.Session:
    if not HIGHLANDER_LINK_COOKIE:
        raise SystemExit(
            "HIGHLANDER_LINK_COOKIE is not set. Log into "
            "https://highlanderlink.ucr.edu in a browser, copy the full Cookie "
            "header from DevTools (Network tab → any request → Request Headers), "
            "and put it in .env.local as HIGHLANDER_LINK_COOKIE=..."
        )
    s = requests.Session()
    s.headers.update(
        {
            "Cookie": HIGHLANDER_LINK_COOKIE,
            "Accept": "application/json",
            "User-Agent": "HighlanderHub-discover/1.0",
        }
    )
    return s


def _check_auth(resp: requests.Response) -> None:
    """Raise SystemExit if Engage bounced us to the login page."""
    for hop in resp.history:
        if "/Account/Login" in hop.headers.get("Location", ""):
            raise SystemExit(
                "Highlander Link cookie expired or invalid — log in via "
                "browser, copy a fresh session cookie, update "
                "HIGHLANDER_LINK_COOKIE in .env.local."
            )


def _get_json(s: requests.Session, url: str, params: dict | None = None) -> Any:
    """GET with backoff on 429/403 and one retry on transient network errors."""
    for attempt in (1, 2):
        try:
            resp = s.get(url, params=params, timeout=TIMEOUT_S, allow_redirects=True)
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt == 1:
                log.warning("%s: %s — retrying in %ss", url, e, NETWORK_RETRY_S)
                time.sleep(NETWORK_RETRY_S)
                continue
            raise
        _check_auth(resp)
        if resp.status_code in (429, 403):
            if attempt == 1:
                log.warning("%s returned %d, backing off %ss", url, resp.status_code, BACKOFF_S)
                time.sleep(BACKOFF_S)
                continue
            raise SystemExit(
                f"{url} returned {resp.status_code} twice — likely rate-limited or blocked. "
                "Aborting without writing accounts.json."
            )
        # Detail endpoint returns 200 + HTML when the org has been React-rendered
        # rather than served as JSON. Treat that as a per-org parse failure so
        # the >10% guard catches a wholesale shape change.
        ct = resp.headers.get("Content-Type", "")
        if "json" not in ct.lower():
            raise ValueError(f"expected JSON, got {ct!r}")
        return resp.json()
    return None  # unreachable, but mypy-friendly


def _iter_orgs(s: requests.Session) -> Iterable[dict[str, Any]]:
    """Paginate the search endpoint until exhausted."""
    skip = 0
    while True:
        page = _get_json(
            s,
            BASE_URL + SEARCH_PATH,
            params={"orderBy[0]": "UpperName asc", "top": PAGE_SIZE, "skip": skip},
        )
        rows = page.get("value") or []
        if not rows:
            return
        for row in rows:
            yield row
        if len(rows) < PAGE_SIZE:
            return
        skip += PAGE_SIZE
        _jitter()


def _normalize_handle(raw: str | None) -> str | None:
    """Turn any IG URL/handle variant into a bare lowercase username."""
    if not raw:
        return None
    s = raw.strip()
    m = IG_URL_RE.search(s)
    if m:
        s = m.group(1)
    s = s.lstrip("@").rstrip("/").lower()
    s = s.split("?", 1)[0].split("/", 1)[0]
    if not s or not re.fullmatch(r"[a-z0-9_.]+", s):
        return None
    return s


def _extract_handle_from_text(html: str | None) -> str | None:
    """Regex fallback over description HTML (or plain text)."""
    if not html:
        return None
    cleaned = BeautifulSoup(html, "html.parser").get_text(" ")
    m = IG_URL_RE.search(cleaned)
    if not m:
        return None
    return _normalize_handle(m.group(1))


def _map_category(category_names: Any) -> str:
    """Convert Highlander Link's CategoryNames into a single slug."""
    if not isinstance(category_names, list) or not category_names:
        return "club"
    first = category_names[0]
    if not isinstance(first, str) or not first.strip():
        return "club"
    # "Academic/Professional" → "academic-professional"
    return first.strip().lower().replace(" ", "-").replace("/", "-").replace("&", "and")


def _extract_handle(detail: dict[str, Any]) -> str | None:
    """Pull an IG handle off a /organization/<id> detail payload."""
    socials = detail.get("socialMedia") or {}
    handle = _normalize_handle(socials.get("InstagramUrl"))
    if handle:
        return handle
    return _extract_handle_from_text(detail.get("description"))


def _merge_accounts(
    existing: list[dict[str, Any]], discovered: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge discovered into existing; existing wins on handle conflict."""
    by_handle: dict[str, dict[str, Any]] = {}
    for entry in existing:
        h = _normalize_handle(entry.get("handle"))
        if h:
            by_handle[h] = {**entry, "handle": h}
    for entry in discovered:
        h = entry["handle"]
        if h in by_handle:
            continue
        by_handle[h] = entry
    return sorted(by_handle.values(), key=lambda e: e["handle"])


def _load_existing() -> list[dict[str, Any]]:
    if not ACCOUNTS_FILE.exists():
        return []
    with ACCOUNTS_FILE.open() as f:
        return json.load(f).get("accounts", [])


def _write_atomic(accounts: list[dict[str, Any]]) -> None:
    tmp = ACCOUNTS_FILE.with_suffix(ACCOUNTS_FILE.suffix + ".tmp")
    payload = {"accounts": accounts}
    with tmp.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    os.replace(tmp, ACCOUNTS_FILE)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    s = _session()

    # Step 1: collect active+public orgs from the search endpoint.
    candidates: list[dict[str, Any]] = []
    for org in _iter_orgs(s):
        if org.get("Status") != "Active":
            continue
        if org.get("Visibility") not in (None, "Public"):
            continue
        candidates.append(org)
    log.info("Found %d active public orgs", len(candidates))

    # Step 2: fetch each org's detail for its structured InstagramUrl.
    discovered: list[dict[str, Any]] = []
    seen_handles: set[str] = set()
    parse_failures = 0

    for i, org in enumerate(candidates, 1):
        org_id = org.get("Id")
        slug = org.get("WebsiteKey") or org_id
        if not org_id:
            continue

        _jitter()
        try:
            detail = _get_json(s, f"{BASE_URL}{DETAIL_PATH}/{org_id}")
        except Exception as e:  # noqa: BLE001
            log.warning("%s: detail fetch failed: %s", slug, e)
            parse_failures += 1
            continue

        try:
            handle = _extract_handle(detail)
        except (KeyError, TypeError, AttributeError) as e:
            log.warning("%s: parse failed (%s)", slug, e)
            parse_failures += 1
            continue

        if not handle or handle in seen_handles:
            continue
        seen_handles.add(handle)

        discovered.append(
            {
                "handle": handle,
                "label": org.get("Name") or detail.get("name") or handle,
                "category": _map_category(org.get("CategoryNames")),
            }
        )
        if i % 50 == 0:
            log.info("progress: %d/%d orgs, %d handles so far", i, len(candidates), len(discovered))

    if candidates and parse_failures / len(candidates) > MAX_PARSE_FAIL_RATIO:
        raise SystemExit(
            f"Aborting: {parse_failures}/{len(candidates)} orgs failed to parse "
            f"(> {int(MAX_PARSE_FAIL_RATIO * 100)}%). API contract likely shifted."
        )

    existing = _load_existing()
    merged = _merge_accounts(existing, discovered)
    new_count = len(merged) - len(existing)
    _write_atomic(merged)

    log.info(
        "Done: %d orgs scanned, %d had IG handles, %d new (total %d in accounts.json)",
        len(candidates),
        len(discovered),
        new_count,
        len(merged),
    )


if __name__ == "__main__":
    sys.exit(main())
