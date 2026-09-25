"""Fetch missing club profile pictures from Instagram.

Each picture is a 128px WebP at ``public/club-avatars/<handle>.webp``, listed
in ``src/lib/club-avatars.json``. The web app renders a monogram for every
club without one. Pictures already in the manifest, including hand-placed
``"manual"`` files, are left in place.

``--instagram-gaps`` buys one profile-only hpix run for every roster club
that still has no picture, at $0.00299 per profile.

Usage:
    python pipeline/club_avatars.py --instagram-gaps --dry-run
    python pipeline/club_avatars.py --instagram-gaps
    python pipeline/club_avatars.py --instagram-gaps --only acm_ucr,cyber_ucr
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageOps

from apify_posts import HPIX_ACTOR_ID, HPIX_BUILD, ApifyClient, hpix_input
from post_archive import read_json, write_json

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
ACCOUNTS_FILE = ROOT / "accounts.json"
ACTIVITY_FILE = ROOT / "data" / "account_activity.json"
AVATAR_DIR = REPO / "public" / "club-avatars"
MANIFEST_FILE = REPO / "src" / "lib" / "club-avatars.json"
# Run intent, so an interrupted purchase resumes instead of buying twice.
INSTAGRAM_RUN_FILE = ROOT / "data" / "apify_avatar_run.json"

INSTAGRAM = "instagram"
PROFILE_PRICE_USD = 0.00299  # hpix 1.2.17 profile_scraped, Free tier
# Instagram's blank silhouette; a monogram says more than a grey outline.
DEFAULT_PICTURE = "44884218_345707102882519_2446069589734326272_n"
# Mirrors src/lib/events/anonymized-hosts.ts: these hosts never get a face.
ANONYMIZED_HANDLES = {"highlander_opps"}
SIZE = 128
WORK = 512

log = logging.getLogger("pipeline.club_avatars")


def known_clubs() -> dict[str, str]:
    """Handle -> display label for every club the site knows."""
    activity = json.loads(ACTIVITY_FILE.read_text())
    clubs = {handle.lower(): handle for handle in activity}
    clubs.update({account["handle"].lower(): account["label"]
                  for account in json.loads(ACCOUNTS_FILE.read_text())["accounts"]})
    return {handle: label for handle, label in clubs.items() if handle not in ANONYMIZED_HANDLES}


def fetch(session: requests.Session, url: str) -> requests.Response:
    # The image CDN can time out before serving a cached result on a retry.
    for attempt in range(3):
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            if attempt == 2:
                raise
            log.warning("%s: %s; retrying", url, exc)
            time.sleep(15 * (attempt + 1))
    raise AssertionError("unreachable")


def to_avatar(data: bytes) -> bytes:
    """128px WebP, center-cropped the way a profile picture already is."""
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        image = Image.new("RGB", rgba.size, "white")
        image.paste(rgba, mask=rgba.getchannel("A"))
    image = ImageOps.fit(image.convert("RGB"), (WORK, WORK), Image.LANCZOS)
    image = image.resize((SIZE, SIZE), Image.LANCZOS)
    out = io.BytesIO()
    image.save(out, "WEBP", quality=82, method=6)
    return out.getvalue()


def instagram_pictures(expected: dict[str, str]) -> dict[str, str]:
    """Handle -> profile picture URL, from one profile-only hpix run."""
    handles = sorted(expected)
    client = ApifyClient(os.environ.get("APIFY_TOKEN", ""), INSTAGRAM_RUN_FILE)
    payload = hpix_input(profiles=handles, scrape_posts=False, scrape_reels=False,
                         scrape_profile_data=True, posts_per_account=1)
    # _run records the intent before buying and resumes an unconsumed run.
    run = client._run(payload, {"usernames": handles, "actor_id": HPIX_ACTOR_ID, "build": HPIX_BUILD,
                                "consumed": False, "purpose": "avatars"},
                      max_charge=round(len(handles) * PROFILE_PRICE_USD + 0.01, 2), timeout=1800)
    log.info("Apify run %s: %s, charged %s", run["id"], run["status"], run.get("chargedEventCounts"))
    pictures = {}
    for row in client.items(run["defaultDatasetId"]):
        data = row.get("data") if row.get("kind") == "profile" else None
        if not isinstance(data, dict):
            continue
        handle = str(data.get("username") or "").lower()
        # A handle whose numeric ID changed now belongs to someone else.
        if handle not in expected or str(data.get("id")) != expected[handle]:
            continue
        url = data.get("profile_pic_url")
        if isinstance(url, str) and url.startswith("https://") and DEFAULT_PICTURE not in url:
            pictures[handle] = url
    return pictures


def save(session: requests.Session, avatars: dict[str, str], pictures: dict[str, str],
         source: str) -> list[str]:
    """Download each picture; returns the handles whose download failed."""
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    failed = []
    for handle, url in sorted(pictures.items()):
        try:
            response = fetch(session, url)
            (AVATAR_DIR / f"{handle}.webp").write_bytes(to_avatar(response.content))
            avatars[handle] = source
        except Exception as exc:  # one bad image must not sink the batch
            failed.append(handle)
            log.warning("%s: %s", handle, exc)
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="comma-separated handles to consider")
    parser.add_argument("--instagram-gaps", action="store_true",
                        help="buy Instagram pictures for roster clubs that still have none")
    parser.add_argument("--dry-run", action="store_true", help="report the purchase without buying")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not args.instagram_gaps:
        log.error("Pass --instagram-gaps to fill clubs that still have no picture.")
        return 2

    wanted = known_clubs()
    if args.only:
        only = {h.strip().lstrip("@").lower() for h in args.only.split(",")}
        wanted = {handle: label for handle, label in wanted.items() if handle in only}
    manifest = json.loads(MANIFEST_FILE.read_text()) if MANIFEST_FILE.exists() else {"avatars": {}}
    avatars: dict[str, str] = manifest["avatars"]
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "User-Agent": "HighlanderHub-avatars/1.0"})

    # Roster clubs only: their stored user ID guards against reused handles.
    gaps = {account["handle"].lower(): str(account["instagram_user_id"])
            for account in json.loads(ACCOUNTS_FILE.read_text())["accounts"]
            if account["handle"].lower() in wanted and account["handle"].lower() not in avatars
            and account.get("instagram_user_id")}
    log.info("%d roster clubs have no picture; buying them costs about $%.2f",
             len(gaps), len(gaps) * PROFILE_PRICE_USD)
    if args.dry_run or not gaps:
        return 0
    failed = save(session, avatars, instagram_pictures(gaps), INSTAGRAM)
    # Consumed only once saved: until then a rerun re-reads the paid dataset.
    write_json(INSTAGRAM_RUN_FILE, {**read_json(INSTAGRAM_RUN_FILE), "consumed": True})

    manifest["avatars"] = dict(sorted(avatars.items()))
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2) + "\n")
    log.info("%d clubs have pictures; %d downloads failed", len(avatars), len(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
