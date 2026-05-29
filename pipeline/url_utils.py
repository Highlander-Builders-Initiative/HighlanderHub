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

    parsed = urlsplit(text)
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    if not _HTTP_URL_RE.match(text):
        return None
    return text
