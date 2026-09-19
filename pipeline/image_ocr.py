"""Image download and Google Vision OCR for event flyers."""
from __future__ import annotations

import base64
from config import GOOGLE_VISION_API_KEY
VISION_URL = "https://vision.googleapis.com/v1/images:annotate"
DURABLE_FLYER_BUCKET = "event-flyers"


class ImageExpired(Exception):
    """Raised when an Instagram CDN image URL is no longer fetchable."""


def _download_image(url: str | None) -> bytes:
    if not url:
        raise ValueError("media has no image_url")

    import requests
    import instagram_cooldown

    instagram_cooldown.ensure_collection_allowed("post images")
    resp = requests.get(url, timeout=10)
    if resp.status_code in {401, 403, 429}:
        kind = (instagram_cooldown.Kind.THROTTLED if resp.status_code == 429
                else instagram_cooldown.Kind.CHALLENGED)
        instagram_cooldown.pause(
            instagram_cooldown.Block(kind, f"image HTTP {resp.status_code}"),
            "post images", f"First-slide download returned HTTP {resp.status_code}")
    if resp.status_code in {404, 410}:
        raise ImageExpired(f"image URL returned HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp.content


def _vision_ocr(image_bytes: bytes) -> str:
    if not GOOGLE_VISION_API_KEY:
        raise RuntimeError("GOOGLE_VISION_API_KEY is required for Vision OCR")

    import requests

    encoded = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "requests": [
            {
                "image": {"content": encoded},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            }
        ]
    }
    resp = requests.post(
        f"{VISION_URL}?key={GOOGLE_VISION_API_KEY}",
        json=payload,
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    first = (data.get("responses") or [{}])[0]
    if first.get("error"):
        raise RuntimeError(first["error"].get("message") or "Vision OCR failed")
    return ((first.get("fullTextAnnotation") or {}).get("text") or "").strip()
