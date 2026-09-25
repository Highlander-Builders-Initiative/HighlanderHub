"""Image download and Google Vision OCR for event flyers."""
from __future__ import annotations

import base64
import logging
import time
from urllib.parse import urlsplit, urlunsplit

from config import (
    GOOGLE_VISION_API_KEY,
    GOOGLE_VISION_API_KEY_PRIMARY,
    GOOGLE_VISION_API_KEY_SECONDARY,
    GOOGLE_VISION_API_KEY_TERTIARY,
)

log = logging.getLogger("pipeline.image_ocr")
VISION_URL = "https://vision.googleapis.com/v1/images:annotate"
DURABLE_FLYER_BUCKET = "event-flyers"


class ImageExpired(Exception):
    """Raised when an Instagram CDN image URL is no longer fetchable."""


def _download_image(url: str | None) -> bytes:
    if not url:
        raise ValueError("media has no image_url")

    import requests
    # Apify supplies signed CDN URLs; an expired image does not invalidate
    # an Instagram login or warrant a day-long pause of unrelated downloads.
    parts = urlsplit(url)
    # Some regional Instagram hosts resolve only to IPv6. The general CDN
    # serves the same signed path over a route reachable by Actions runners.
    fallback = (urlunsplit(parts._replace(netloc="scontent.cdninstagram.com"))
                if parts.scheme == "https" and (parts.hostname or "").endswith(".fna.fbcdn.net")
                else None)
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=10)
            break
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 2:
                raise
            if fallback:
                url, fallback = fallback, None
                log.info("Retrying image through Instagram's general CDN")
            time.sleep(attempt + 1)
    if resp.status_code in {401, 403, 404, 410}:
        raise ImageExpired(f"image URL returned HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp.content


def _vision_ocr(image_bytes: bytes) -> str:
    if not GOOGLE_VISION_API_KEY_PRIMARY or not GOOGLE_VISION_API_KEY:
        raise RuntimeError(
            "GOOGLE_VISION_API_KEY_PRIMARY (new key) and GOOGLE_VISION_API_KEY "
            "(existing overflow key) are required for Vision OCR"
        )
    keys = {
        "primary": GOOGLE_VISION_API_KEY_PRIMARY,
        "secondary": GOOGLE_VISION_API_KEY_SECONDARY,
        "tertiary": GOOGLE_VISION_API_KEY_TERTIARY,
        "overflow": GOOGLE_VISION_API_KEY,
    }
    configured = [key for key in keys.values() if key]
    if len(configured) != len(set(configured)):
        raise RuntimeError("All configured Vision keys must be different")

    import requests
    from db import client

    encoded = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "requests": [
            {
                "image": {"content": encoded},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            }
        ]
    }
    # Reserve durably before sending: crashes/timeouts may have reached Google.
    # Never refund an uncertain attempt or fall back if accounting is unavailable.
    options = {}
    if GOOGLE_VISION_API_KEY_SECONDARY or GOOGLE_VISION_API_KEY_TERTIARY:
        options = {"p_secondary_enabled": bool(GOOGLE_VISION_API_KEY_SECONDARY),
                   "p_tertiary_enabled": bool(GOOGLE_VISION_API_KEY_TERTIARY)}
    reservation = client().rpc("reserve_vision_ocr_request", options).execute().data
    if not isinstance(reservation, dict) or not keys.get(reservation.get("slot")):
        raise RuntimeError("Invalid Vision usage reservation; no OCR request sent")
    slot = reservation["slot"]
    api_key = keys[slot]
    log.info("Vision OCR: %s key, month %s, attempt %s", slot,
             reservation.get("month"), reservation.get("used"))
    resp = requests.post(
        VISION_URL,
        # Keep credentials out of request URLs and HTTP exception logs.
        headers={"X-Goog-Api-Key": api_key},
        json=payload,
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    first = (data.get("responses") or [{}])[0]
    if first.get("error"):
        raise RuntimeError(first["error"].get("message") or "Vision OCR failed")
    return ((first.get("fullTextAnnotation") or {}).get("text") or "").strip()
