"""Instagram post row policy after occurrence and identity resolution."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Iterable

from category_inference import infer_category_from_text
from classify import classify_content_kind, detect_free_food
from event_dates import midnight_end, normalize_timestamptz, was_stale_when_posted
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


def instagram_event_id(handle: str, media_id: str) -> str | None:
    """Identify the post's single announcement independently of its event date.

    Keep the owner prefix for repeat-ad reconciliation, including private hosts.
    Semantic duplicates are reconciled after publication, never by primary key.
    """
    if not media_id or not re.fullmatch(r"[0-9]+", str(media_id)):
        raise ValueError("Instagram publication requires a numeric post media_id")
    if not handle:
        return None
    return f"ig_{handle}_p{media_id}"


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
    """Apply date, host privacy, classification and RSVP rules to an assessed post."""
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

    event_id = instagram_event_id(identity_handle, raw.get("media_id"))
    if not event_id:
        return None
    description = str(occurrence.get("description") or "")
    tags = _clean_tags(occurrence.get("tags"))
    content_kind = classify_content_kind("instagram", title=title, description=description,
                                         tags=tags, ocr_text=text, assessed_kind=assessed_kind)

    destinations = {url for value in qr_urls if (url := normalize_rsvp_url(value))}
    rsvp_url = (
        (next(iter(destinations)) if len(destinations) == 1 else None)
        or normalize_rsvp_url(occurrence.get("rsvp_url"), text)
        or _caption_rsvp_url(str(raw.get("caption") or ""))
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
        "starts_at": starts_at, "ends_at": ends_at, "all_day": occurrence.get("all_day"),
        "location": str(occurrence.get("location") or "").strip(),
        "host": host, "host_handle": host_handle, "category": category,
        "content_kind": content_kind, "tags": tags, "source": "instagram",
        "source_url": normalize_http_url(raw.get("permalink")),
        "image_url": normalize_http_url(image_url),
        "has_free_food": detect_free_food(text, title, description, *tags),
        "rsvp_required": bool(rsvp_url) or _bool_or_default(occurrence.get("rsvp_required"), False)
                         or bool(_RSVP_TERMS.search(text)),
        "rsvp_url": rsvp_url, "scraped_at": scraped_at,
    }
