"""Fetch club profile pictures into the web app.

Each picture is a 128px WebP at ``public/club-avatars/<handle>.webp``, listed
with its source in ``src/lib/club-avatars.json``. The web app renders a
monogram for every club without one.

Two sources, each replacing only its own manifest entries (a hand-placed
``"manual"`` file is never touched):

* ``highlanderlink`` (default, free): Engage's public directory lists each
  org's logo and, on its detail record, the org's Instagram URL. Orgs whose
  Instagram handle is a club the site knows get their logo.
* ``instagram`` (``--instagram-gaps``, paid): one profile-only hpix run buys
  the Instagram profile picture of every roster club still without one, at
  $0.00299 per profile. Campus offices and departments are not Engage orgs.

Usage:
    python pipeline/club_avatars.py
    python pipeline/club_avatars.py --only acm_ucr,cyber_ucr
    python pipeline/club_avatars.py --instagram-gaps --dry-run
    python pipeline/club_avatars.py --instagram-gaps
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import os
import random
import re
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
ACCOUNTS_FILE = ROOT / "accounts.json"
ACTIVITY_FILE = ROOT / "data" / "account_activity.json"
AVATAR_DIR = REPO / "public" / "club-avatars"
MANIFEST_FILE = REPO / "src" / "lib" / "club-avatars.json"
# Run intent, so an interrupted purchase resumes instead of buying twice.
INSTAGRAM_RUN_FILE = ROOT / "data" / "apify_avatar_run.json"

ENGAGE = "https://highlanderlink.ucr.edu"
IMAGE_BASE = "https://se-images.campuslabs.com/clink/images/"
SOURCE = "highlanderlink"
INSTAGRAM = "instagram"
PROFILE_PRICE_USD = 0.00299  # hpix 1.2.17 profile_scraped, Free tier
# Instagram's blank silhouette; a monogram says more than a grey outline.
DEFAULT_PICTURE = "44884218_345707102882519_2446069589734326272_n"
# Mirrors src/lib/events/anonymized-hosts.ts: these hosts never get a face.
ANONYMIZED_HANDLES = {"highlander_opps"}
SIZE = 128
WORK = 512
TOLERANCE = 24  # per-channel distance still counted as backdrop
IG_URL_RE = re.compile(r"instagram\.com/([A-Za-z0-9_.]+)", re.IGNORECASE)
NOT_HANDLES = {"p", "reel", "reels", "stories", "explore", "accounts"}

log = logging.getLogger("pipeline.club_avatars")


def known_clubs() -> dict[str, str]:
    """Handle -> display label for every club the site knows."""
    activity = json.loads(ACTIVITY_FILE.read_text())
    clubs = {handle.lower(): handle for handle in activity}
    clubs.update({account["handle"].lower(): account["label"]
                  for account in json.loads(ACCOUNTS_FILE.read_text())["accounts"]})
    return {handle: label for handle, label in clubs.items() if handle not in ANONYMIZED_HANDLES}


def same_org(name: str, label: str) -> bool:
    """Engage names and roster labels differ mostly by an "at UCR" suffix."""
    def core(text: str) -> str:
        text = re.sub(r"(\bat|@)\s*(ucr|uc riverside)\b", "", text.lower())
        return re.sub(r"[^a-z0-9]", "", text)
    name, label = core(name), core(label)
    return bool(name and label) and (name in label or label in name)


def instagram_handle(text: str | None) -> str | None:
    for match in IG_URL_RE.finditer(text or ""):
        handle = match.group(1).rstrip(".").lower()
        if handle not in NOT_HANDLES:
            return handle
    return None


def fetch(session: requests.Session, url: str, **params) -> requests.Response:
    # The image CDN resizes large originals on first request and can time
    # out (502/504) before serving the cached result on a retry.
    for attempt in range(3):
        try:
            response = session.get(url, params=params or None, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            if attempt == 2:
                raise
            log.warning("%s: %s; retrying", url, exc)
            time.sleep(15 * (attempt + 1))
    raise AssertionError("unreachable")


def engage_logos(session: requests.Session, wanted: dict[str, str]) -> dict[str, str]:
    """Map Instagram handle -> Engage picture file for clubs with a logo."""
    orgs, skip = [], 0
    while True:
        page = fetch(session, f"{ENGAGE}/api/discovery/search/organizations",
                     **{"orderBy[0]": "UpperName asc", "top": 100, "skip": skip}).json()
        rows = page.get("value") or []
        if not rows:
            break
        orgs += rows
        skip += len(rows)
    log.info("Highlander Link lists %d orgs", len(orgs))

    claims: dict[str, list[dict]] = {}
    for index, org in enumerate(orgs, 1):
        detail = fetch(session, f"{ENGAGE}/api/discovery/organization/{org['Id']}").json()
        # The structured field is empty for some orgs that link Instagram in
        # their description instead.
        handle = (instagram_handle((detail.get("socialMedia") or {}).get("InstagramUrl"))
                  or instagram_handle(org.get("Description")))
        if handle in wanted:
            claims.setdefault(handle, []).append(org)
        if index % 100 == 0:
            log.info("checked %d/%d orgs", index, len(orgs))
        time.sleep(random.uniform(0.3, 0.7))

    found: dict[str, str] = {}
    for handle, orgs_for_handle in claims.items():
        # Offices list a shared feed (Commuter Programs links @ucrstudentlife),
        # so a multiply-claimed account only takes the logo of its namesake.
        if len(orgs_for_handle) > 1:
            orgs_for_handle = [org for org in orgs_for_handle if same_org(org["Name"], wanted[handle])]
            if len(orgs_for_handle) != 1:
                log.info("%s: claimed by several orgs, none clearly its own; skipped", handle)
                continue
        if orgs_for_handle[0].get("ProfilePicture"):
            found[handle] = orgs_for_handle[0]["ProfilePicture"]
    return found


def flat_background(image: Image.Image) -> tuple[int, int, int] | None:
    """The backdrop color when the border is mostly one color, else None."""
    width, height = image.size
    border = ([image.getpixel((x, 0)) for x in range(width)]
              + [image.getpixel((x, height - 1)) for x in range(width)]
              + [image.getpixel((0, y)) for y in range(height)]
              + [image.getpixel((width - 1, y)) for y in range(height)])
    background = tuple(sorted(channel)[len(channel) // 2] for channel in zip(*border))
    near = sum(max(abs(a - b) for a, b in zip(pixel, background)) <= TOLERANCE for pixel in border)
    return background if near >= 0.6 * len(border) else None


def circle_ready(image: Image.Image) -> Image.Image:
    """Square the image so a circular crop shows the whole mark.

    Logos on a flat backdrop often run text into the corners or come as wide
    wordmarks; they are recentered and shrunk inside the circle, padded with
    that backdrop. Photos (no flat border) crop to the center like any
    profile picture.
    """
    image = image.convert("RGB")
    image.thumbnail((WORK, WORK), Image.LANCZOS)
    background = flat_background(image)
    if background is None:
        return ImageOps.fit(image, (WORK, WORK), Image.LANCZOS)

    distance = Image.merge("RGB", [band.point(lambda v, c=c: abs(v - c))
                                   for band, c in zip(image.split(), background)])
    # Median filtering drops isolated JPEG specks that would inflate the box.
    mask = (distance.convert("L").point(lambda v: 255 if v > TOLERANCE else 0)
            .filter(ImageFilter.MedianFilter(3)))
    box = mask.getbbox()
    if box is None:
        return Image.new("RGB", (WORK, WORK), background)
    content, mask = image.crop(box), mask.crop(box)
    cx, cy = (content.width - 1) / 2, (content.height - 1) / 2
    pixels = mask.load()
    reach = max((((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                 for y in range(0, content.height, 2) for x in range(0, content.width, 2)
                 if pixels[x, y]), default=1.0)
    # Never enlarge past the source's own scale; only shrink to fit.
    scale = min(0.92 * WORK / 2 / max(reach, 1.0), WORK / max(image.size))
    content = content.resize((max(1, round(content.width * scale)),
                              max(1, round(content.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGB", (WORK, WORK), background)
    canvas.paste(content, ((WORK - content.width) // 2, (WORK - content.height) // 2))
    return canvas


def to_avatar(data: bytes, *, logo: bool = True) -> bytes:
    """128px WebP. Instagram pictures (``logo=False``) are already made for a
    circle, so only Engage logos get recentered inside one."""
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        image = Image.new("RGB", rgba.size, "white")
        image.paste(rgba, mask=rgba.getchannel("A"))
    image = circle_ready(image) if logo else ImageOps.fit(image.convert("RGB"), (WORK, WORK), Image.LANCZOS)
    image = image.resize((SIZE, SIZE), Image.LANCZOS)
    out = io.BytesIO()
    image.save(out, "WEBP", quality=82, method=6)
    return out.getvalue()


def instagram_pictures(expected: dict[str, str]) -> dict[str, str]:
    """Handle -> profile picture URL, from one profile-only hpix run."""
    from apify_posts import HPIX_ACTOR_ID, HPIX_BUILD, ApifyClient, hpix_input

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
         source: str, **params) -> list[str]:
    """Download each picture; returns the handles whose download failed."""
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    failed = []
    for handle, url in sorted(pictures.items()):
        try:
            response = fetch(session, url, **params)
            (AVATAR_DIR / f"{handle}.webp").write_bytes(to_avatar(response.content, logo=source == SOURCE))
            avatars[handle] = source
        except Exception as exc:  # one bad image must not sink the batch
            failed.append(handle)
            log.warning("%s: %s", handle, exc)
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="comma-separated handles to refresh")
    parser.add_argument("--instagram-gaps", action="store_true",
                        help="buy Instagram pictures for roster clubs that still have none")
    parser.add_argument("--dry-run", action="store_true", help="report matches without writing or buying")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    wanted = known_clubs()
    if args.only:
        only = {h.strip().lstrip("@").lower() for h in args.only.split(",")}
        wanted = {handle: label for handle, label in wanted.items() if handle in only}
    manifest = json.loads(MANIFEST_FILE.read_text()) if MANIFEST_FILE.exists() else {"avatars": {}}
    avatars: dict[str, str] = manifest["avatars"]
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "User-Agent": "HighlanderHub-avatars/1.0"})

    if args.instagram_gaps:
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
        from post_archive import read_json, write_json
        # Consumed only once saved: until then a rerun re-reads the paid dataset.
        write_json(INSTAGRAM_RUN_FILE, {**read_json(INSTAGRAM_RUN_FILE), "consumed": True})
    else:
        # Only this source's own entries are ours to replace.
        targets = {h: label for h, label in wanted.items() if avatars.get(h, SOURCE) == SOURCE}
        logos = engage_logos(session, targets)
        log.info("%d of %d clubs have a Highlander Link logo", len(logos), len(targets))
        if args.dry_run:
            return 0
        failed = save(session, avatars, {h: IMAGE_BASE + picture for h, picture in logos.items()},
                      SOURCE, preset="large-sq")
        # A club that dropped its logo loses the stale picture too.
        for handle in targets.keys() - logos.keys():
            if avatars.pop(handle, None):
                (AVATAR_DIR / f"{handle}.webp").unlink(missing_ok=True)

    manifest["avatars"] = dict(sorted(avatars.items()))
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2) + "\n")
    log.info("%d clubs have pictures; %d downloads failed", len(avatars), len(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
