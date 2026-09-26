"""Shared URL normalization for event pipeline mappers."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit


_URL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+\-.]*:", re.IGNORECASE)
_HTTP_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def normalize_http_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.startswith("//"):
        text = f"https:{text}"
    elif not _URL_SCHEME_RE.match(text):
        text = f"https://{text}"

    try:
        parsed = urlsplit(text)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    if not _HTTP_URL_RE.match(text):
        return None
    return text


def normalize_rsvp_url(value: Any, ocr_text: str = "") -> str | None:
    """A registration destination, with narrowly supported short-link repair.

    Only join OCR-inserted spaces when the entire short link occupies a source
    line. Do not turn arbitrary model prose ("link in bio") into a URL.
    """
    normalized = normalize_http_url(value)
    if normalized is None and isinstance(value, str):
        candidate = value.strip()
        short_link = re.compile(
            r"(?:https?://)?(?:bit\.ly|tinyurl\.com|forms\.gle)/"
            r"[\w-]+(?:[ \t]+[\w-]+)+", re.IGNORECASE,
        )
        if short_link.fullmatch(candidate) and any(
            line.strip().casefold() == candidate.casefold()
            for line in ocr_text.splitlines()
        ):
            normalized = normalize_http_url(re.sub(r"[ \t]+", "", candidate))
    if normalized is None:
        return None
    parsed = urlsplit(normalized)
    host = (parsed.hostname or "").lower()
    if host == "instagram.com" or host.endswith(".instagram.com") or host == "instagr.am":
        return None
    # A shortener's homepage cannot identify the registration form.
    if host.removeprefix("www.") in {"bit.ly", "tinyurl.com", "forms.gle"} and not parsed.path.strip("/"):
        return None
    # Directions to the venue ("scan for the Google Map location") are not a
    # signup, however prominently the flyer prints their QR code.
    if _is_map_url(host.removeprefix("www."), parsed.path):
        return None
    return normalized


_MAP_HOSTS = frozenset({"maps.app.goo.gl", "maps.google.com", "maps.apple.com", "maps.apple",
                        "waze.com", "ul.waze.com"})


def _is_map_url(host: str, path: str) -> bool:
    if host in _MAP_HOSTS or host.startswith("maps.google."):
        return True
    first = path.strip("/").split("/", 1)[0].lower()
    return ((host == "goo.gl" and first == "maps")
            or (re.fullmatch(r"google\.[a-z.]+", host) is not None and first == "maps"))
