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
            "GOOGLE_VISION_API_KEY (first allowance) and GOOGLE_VISION_API_KEY_PRIMARY "
            "(overflow key) are required for Vision OCR"
        )
    # The existing key takes the first monthly allowance; the newer
    # _PRIMARY key receives uncapped overflow, including paid usage.
    keys = {
        "primary": GOOGLE_VISION_API_KEY,
        "secondary": GOOGLE_VISION_API_KEY_SECONDARY,
        "tertiary": GOOGLE_VISION_API_KEY_TERTIARY,
        "overflow": GOOGLE_VISION_API_KEY_PRIMARY,
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
    for attempt in range(3):
        # Retries consume a fresh reservation too. Accounting errors must escape
        # the retry handler without sending another unaccounted request.
        reservation = client().rpc("reserve_vision_ocr_request", options).execute().data
        if not isinstance(reservation, dict) or not keys.get(reservation.get("slot")):
            raise RuntimeError("Invalid Vision usage reservation; no OCR request sent")
        slot = reservation["slot"]
        log.info("Vision OCR: %s key, month %s, usage %s, image attempt %d/3", slot,
                 reservation.get("month"), reservation.get("used"), attempt + 1)
        try:
            resp = requests.post(
                VISION_URL,
                # Keep credentials out of request URLs and HTTP exception logs.
                headers={"X-Goog-Api-Key": keys[slot]},
                json=payload,
                timeout=20,
            )
            resp.raise_for_status()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status not in {408, 429, 500, 502, 503, 504} or attempt == 2:
                raise
            reason = f"HTTP {status}"
        except (requests.ConnectionError, requests.Timeout) as exc:
            if attempt == 2:
                raise
            reason = type(exc).__name__
        else:
            data = resp.json()
            first = (data.get("responses") or [{}])[0]
            error = first.get("error")
            if not error:
                return ((first.get("fullTextAnnotation") or {}).get("text") or "").strip()
            code = error.get("code")
            message = error.get("message") or "Vision OCR failed"
            reason = f"Vision OCR failed (HTTP {resp.status_code}, code {code}): {message}"
            # Per-image errors can arrive in HTTP 200 responses. google.rpc.Code:
            # DEADLINE_EXCEEDED, RESOURCE_EXHAUSTED, INTERNAL, UNAVAILABLE.
            if code not in {4, 8, 13, 14} or attempt == 2:
                raise RuntimeError(reason)
        delay = 2 ** attempt
        log.warning("Vision OCR retry after %s; waiting %ss", reason, delay)
        time.sleep(delay)
