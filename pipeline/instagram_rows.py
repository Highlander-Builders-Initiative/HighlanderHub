"""Shared Instagram row policy after story/post occurrence and identity resolution."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Iterable

from category_inference import infer_category_from_text
from classify import classify_content_kind, detect_free_food
from story_dates import midnight_end, normalize_timestamptz, was_stale_when_posted
from url_utils import normalize_http_url, normalize_rsvp_url

log = logging.getLogger("pipeline.instagram_rows")

EVENT_CATEGORIES = ("club", "academic", "social", "career", "sports", "arts", "community", "free_food")
_ANONYMIZED_HOST_HANDLES = frozenset({"highlander_opps"})
_RSVP_TERMS = re.compile(
    r"\b(rsvp|registration|register|sign[-\s]?ups?|tickets?|reserve your|"
    r"limited (?:spots|slots|seats)|link in bio)\b", re.I)
_CAPTION_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.I)


def _clean_tags(value: Any) -> list[str]:
    return [tag for item in value if (tag := str(item).strip())] if isinstance(value, list) else []


def _bool_or_default(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        value = value.strip().lower()
        if value in {"true", "1", "yes", "y"}:
            return True
        if value in {"false", "0", "no", "n"}:
            return False
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return default


def instagram_event_id(handle: str, starts_at: str) -> str | None:
    start = normalize_timestamptz(starts_at)
    if not handle or not start:
        return None
    return f"ig_{handle}_{datetime.fromisoformat(start).strftime('%Y%m%dT%H%MZ')}"


def _caption_rsvp_url(caption: str) -> str | None:
    for candidate in _CAPTION_URL.findall(caption):
        normalized = normalize_rsvp_url(candidate.rstrip(".,;:!?\"'"))
        if normalized:
            return normalized
    return None


def build_instagram_row(
    raw: dict, occurrence: dict, *, identity_handle: str, host_handle: str,
    account_meta: dict, text: str, image_url: str | None, qr_urls: Iterable,
    scraped_at: str, assessed_kind: str | None,
) -> dict | None:
    """Apply the same dates, host privacy, classification and RSVP rules to both channels.

    Adapters resolve source-specific identities, supported occurrences and flyer
    selection. `text` includes OCR and captions; `occurrence` may retain legacy
    story fields such as category, tags, price and description. Classification
    is returned for every row; publication eligibility belongs to the caller.
    """
    title = str(occurrence.get("title") or "").strip()
    starts_at = normalize_timestamptz(occurrence.get("starts_at"))
    if not title or not starts_at:
        return None
    ends_at = midnight_end(text, starts_at, normalize_timestamptz(occurrence.get("ends_at")))
    if ends_at and datetime.fromisoformat(ends_at) <= datetime.fromisoformat(starts_at):
        ends_at = None
    if was_stale_when_posted(raw, starts_at, ends_at):
        log.info("instagram %s: skipping event already stale when media was posted (%s)",
                 raw.get("media_id") or raw.get("id"), starts_at)
        return None

    event_id = instagram_event_id(identity_handle, starts_at)
    if not event_id:
        return None
    description = str(occurrence.get("description") or "")
    tags = _clean_tags(occurrence.get("tags"))
    content_kind = classify_content_kind("instagram", title=title, description=description,
                                         tags=tags, ocr_text=text, assessed_kind=assessed_kind)

    destinations = {url for value in qr_urls if (url := normalize_rsvp_url(value))}
    rsvp_url = (
        normalize_rsvp_url(raw.get("story_cta_url"))
        or (next(iter(destinations)) if len(destinations) == 1 else None)
        or normalize_rsvp_url(occurrence.get("rsvp_url"), text)
        or _caption_rsvp_url(str(raw.get("caption") or ""))
        or _caption_rsvp_url(str((raw.get("reshared_post") or {}).get("caption") or ""))
    )
    if raw.get("handle") in _ANONYMIZED_HOST_HANDLES or host_handle in _ANONYMIZED_HOST_HANDLES:
        host, host_handle = "", None
    else:
        host = account_meta.get("label") or host_handle
    category = occurrence.get("category")
    if not isinstance(category, str) or category not in EVENT_CATEGORIES:
        category = infer_category_from_text(title, f"{description}\n{text}")

    return {
        "id": event_id, "title": title[:200], "description": description,
        "starts_at": starts_at, "ends_at": ends_at,
        "location": str(occurrence.get("location") or "").strip(),
        "host": host, "host_handle": host_handle, "category": category,
        "content_kind": content_kind, "tags": tags, "source": "instagram",
        "source_url": normalize_http_url(raw.get("permalink")),
        "image_url": normalize_http_url(image_url),
        "is_free": _bool_or_default(occurrence.get("is_free"), True),
        "has_free_food": detect_free_food(text, title, description, *tags),
        "rsvp_required": bool(rsvp_url) or _bool_or_default(occurrence.get("rsvp_required"), False)
                         or bool(_RSVP_TERMS.search(text)),
        "rsvp_url": rsvp_url, "scraped_at": scraped_at,
    }
