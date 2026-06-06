"""Extract structured events from raw Instagram story image flyers.

Reads raw story JSON from data/raw/<handle>/, runs OCR + Gemini extraction for
uncached image stories, caches terminal results in data/extracted/, then writes
event-shaped rows to Supabase.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from config import (
    EXTRACTED_DIR,
    GOOGLE_CLOUD_LOCATION,
    GOOGLE_CLOUD_PROJECT,
    GOOGLE_VISION_API_KEY,
    RAW_DIR,
    ensure_dirs,
    load_accounts,
)
from classify import classify_content_kind, detect_free_food
from discord_notify import notify_free_food_events
from event_identity import dedupe_event_rows, suppress_tombstoned_event_groups
from url_utils import normalize_http_url as _normalize_url

log = logging.getLogger("pipeline.extract_stories")

VISION_URL = "https://vision.googleapis.com/v1/images:annotate"
GEMINI_MODEL = "gemini-2.5-flash-lite"
EVENT_CATEGORIES = (
    "club",
    "academic",
    "social",
    "career",
    "sports",
    "arts",
    "community",
    "free_food",
)
# Categories the LLM may assign. `free_food` is excluded: free food is detected
# deterministically (see classify.detect_free_food / has_free_food), so the model
# always picks the event's real type. `free_food` stays valid for storage so
# legacy/cached rows that predate the split still round-trip until they expire.
LLM_EVENT_CATEGORIES = tuple(c for c in EVENT_CATEGORIES if c != "free_food")
REMOTE_CACHE_TERMINAL_STATUSES = {"ok", "not_event", "no_text", "image_expired"}
DURABLE_FLYER_BUCKET = "event-flyers"
# Instagram handles that must not appear as the public "hosted by" name on listings.
_ANONYMIZED_HOST_HANDLES = frozenset({"highlander_opps"})
PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_OCR_DATE_RE = re.compile(
    r"\b("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?|tember)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?"
    r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b",
    re.IGNORECASE,
)
_OCR_TIME_RANGE_RE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)"
    r"(?:\s*(?:-|to)\s*|\s+)"
    r"(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)\b",
    re.IGNORECASE,
)
# Compact ranges like "1-2 pm" apply the trailing meridiem to both endpoints.
_OCR_COMPACT_TIME_RANGE_RE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(?:-|to)\s*"
    r"(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)\b",
    re.IGNORECASE,
)

GEMINI_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_event": {"type": "boolean"},
        "title": {"type": "string", "nullable": True},
        "description": {"type": "string"},
        "starts_at": {"type": "string", "nullable": True},
        "ends_at": {"type": "string", "nullable": True},
        "location": {"type": "string"},
        "category": {"type": "string", "enum": list(LLM_EVENT_CATEGORIES)},
        "tags": {"type": "array", "items": {"type": "string"}},
        "is_free": {"type": "boolean"},
        "rsvp_required": {"type": "boolean"},
        "rsvp_url": {"type": "string", "nullable": True},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": [
        "is_event",
        "title",
        "description",
        "starts_at",
        "ends_at",
        "location",
        "category",
        "tags",
        "is_free",
        "rsvp_required",
        "rsvp_url",
        "confidence",
    ],
}


class ImageExpired(Exception):
    """Raised when an Instagram CDN image URL is no longer fetchable."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_path(story_id: str) -> Path:
    return EXTRACTED_DIR / f"{story_id}.json"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _write_cache(story_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(story_id)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    return payload


def _remote_cache_row_to_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    status = row.get("status")
    if status not in REMOTE_CACHE_TERMINAL_STATUSES:
        return None

    payload: dict[str, Any] = {
        "status": status,
        "story_id": str(row.get("story_id") or ""),
        "handle": str(row.get("handle") or ""),
        "extracted_at": row.get("extracted_at") or _utc_now(),
    }
    if row.get("ocr_text") is not None:
        payload["ocr_text"] = row.get("ocr_text")
    if row.get("image_url") is not None:
        payload["image_url"] = row.get("image_url")
    if row.get("result") is not None:
        payload["result"] = row.get("result")
    return payload


def _load_remote_cache(story_id: str) -> dict[str, Any] | None:
    try:
        from db import client

        response = (
            client()
            .table("story_extractions")
            .select("story_id,handle,status,ocr_text,image_url,result,extracted_at")
            .eq("story_id", story_id)
            .maybe_single()
            .execute()
        )
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - remote cache is best-effort.
        log.warning("story_extractions: cache lookup failed for %s: %s", story_id, exc)
        return None

    row = getattr(response, "data", None)
    if not isinstance(row, dict):
        return None
    return _remote_cache_row_to_payload(row)


def _write_remote_cache(payload: dict[str, Any]) -> None:
    status = payload.get("status")
    if status not in REMOTE_CACHE_TERMINAL_STATUSES:
        return

    row = {
        "story_id": payload.get("story_id"),
        "handle": payload.get("handle"),
        "status": status,
        "ocr_text": payload.get("ocr_text"),
        "image_url": payload.get("image_url"),
        "result": payload.get("result"),
        "extracted_at": payload.get("extracted_at") or _utc_now(),
    }
    if not row["story_id"]:
        return

    try:
        from db import upsert_batched

        upsert_batched("story_extractions", [row], on_conflict="story_id")
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - local cache remains authoritative.
        log.warning(
            "story_extractions: cache write failed for %s: %s",
            row["story_id"],
            exc,
        )


def _persist_terminal_cache(story_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    cached = _write_cache(story_id, payload)
    _write_remote_cache(cached)
    return cached


def _load_account_meta() -> dict[str, dict[str, Any]]:
    return {a["handle"]: a for a in load_accounts()}


def _iter_raw_stories(known_handles: set[str]) -> Iterable[dict[str, Any]]:
    if not RAW_DIR.exists():
        return
    for handle_dir in sorted(RAW_DIR.iterdir()):
        if not handle_dir.is_dir() or handle_dir.name not in known_handles:
            continue
        for path in sorted(handle_dir.glob("*.json")):
            try:
                yield _read_json(path)
            except json.JSONDecodeError:
                log.warning("skipping malformed file: %s", path)


def _download_image(url: str | None) -> bytes:
    if not url:
        raise ValueError("story has no image_url")

    import requests

    resp = requests.get(url, timeout=10)
    if resp.status_code in {403, 404, 410}:
        raise ImageExpired(f"image URL returned HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp.content


def _storage_object_path(raw: dict[str, Any]) -> str | None:
    story_id = str(raw.get("id") or "")
    handle = str(raw.get("handle") or "")
    safe_story_id = re.sub(r"[^A-Za-z0-9_-]+", "", story_id)
    safe_handle = re.sub(r"[^A-Za-z0-9_.-]+", "_", handle).strip("._-")
    if not safe_story_id or not safe_handle:
        return None
    return f"instagram/{safe_handle}/{safe_story_id}.jpg"


def _upload_story_flyer(raw: dict[str, Any], image_bytes: bytes) -> str | None:
    path = _storage_object_path(raw)
    if path is None:
        return None

    try:
        from db import client

        bucket = client().storage.from_(DURABLE_FLYER_BUCKET)
        bucket.upload(
            path,
            image_bytes,
            {
                "content-type": "image/jpeg",
                "cache-control": "31536000",
                "upsert": "true",
            },
        )
        return bucket.get_public_url(path)
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - extraction can still proceed.
        log.warning("event flyer upload failed for %s: %s", path, exc)
        return None


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


def _build_gemini_prompt(
    raw: dict[str, Any],
    meta: dict[str, Any],
    ocr_text: str,
) -> str:
    context = {
        "ocr_text": ocr_text,
        "instagram_handle": raw.get("handle"),
        "account_label": meta.get("label"),
        "account_category": meta.get("category"),
        "story_caption": raw.get("caption"),
        "story_cta_url": raw.get("story_cta_url"),
        "posted_at": raw.get("posted_at"),
        "category_values": list(LLM_EVENT_CATEGORIES),
    }
    return (
        "Extract a UC Riverside campus event from this Instagram story flyer. "
        "Return JSON only. If the flyer is not advertising a specific event, "
        "set is_event to false and keep title and starts_at null. Infer the "
        "year from posted_at when a date omits the year. UCR is in Riverside, "
        "California, so interpret flyer times as America/Los_Angeles local "
        "wall time unless the OCR explicitly gives another timezone. Do not "
        "change an explicit OCR date based on relative text like THIS SUNDAY "
        "or NEXT SUNDAY. Some flyers are weekly schedule grids with one column "
        "per day, and some day columns list no event; never use a day with no "
        "listed activity as starts_at and never invent a time that is not "
        "printed for that day — anchor starts_at on the first day and time that "
        "actually has an event. For ranges like 11:00 AM 2:00 PM, use 11:00 AM as "
        "starts_at and 2:00 PM as ends_at on the same OCR date. Return "
        "starts_at and ends_at as ISO-8601 timestamps with the correct Pacific "
        "timezone offset for that date. Prefer exact text from OCR over "
        "guessing; if the OCR date or time is ambiguous, set starts_at and "
        "ends_at null with low confidence.\n\n"
        f"{json.dumps(context, indent=2, sort_keys=True)}"
    )


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _gemini_extract(
    raw: dict[str, Any],
    meta: dict[str, Any],
    ocr_text: str,
) -> dict[str, Any]:
    try:
        from google import genai
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "google-genai is required for Gemini extraction. Run this script "
            "with the pipeline virtualenv (`pipeline/.venv/bin/python "
            "pipeline/extract_stories.py`) or install dependencies with "
            "`pip install -r pipeline/requirements.txt`."
        ) from exc

    client = genai.Client(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT or None,
        location=GOOGLE_CLOUD_LOCATION or "global",
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=_build_gemini_prompt(raw, meta, ocr_text),
        config={
            "response_mime_type": "application/json",
            "response_schema": GEMINI_RESPONSE_SCHEMA,
        },
    )

    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, dict):
        return parsed
    if hasattr(parsed, "model_dump"):
        return parsed.model_dump()

    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini returned no JSON text")
    return json.loads(_strip_json_fence(text))


def _process_story(raw: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    story_id = str(raw.get("id") or "")
    handle = str(raw.get("handle") or "")
    label = f"ig_{handle}_{story_id}" if handle and story_id else story_id or "unknown"

    if not story_id:
        log.warning("extract %s: missing story id", label)
        return {"status": "error", "error": "missing story id"}


    cache = _cache_path(story_id)
    if cache.exists():
        cached = _read_json(cache)
        log.info("extract %s: cache %s", label, cached.get("status"))
        return cached

    remote_cached = _load_remote_cache(story_id)
    if (
        remote_cached is not None
        and remote_cached.get("status") in REMOTE_CACHE_TERMINAL_STATUSES
    ):
        log.info("extract %s: remote cache %s", label, remote_cached.get("status"))
        return _write_cache(story_id, remote_cached)

    try:
        image = _download_image(raw.get("image_url"))
    except ImageExpired as exc:
        payload = {
            "status": "image_expired",
            "error": str(exc),
            "story_id": story_id,
            "handle": handle,
            "extracted_at": _utc_now(),
        }
        log.info("extract %s: image_expired", label)
        return _persist_terminal_cache(story_id, payload)
    except Exception as exc:  # noqa: BLE001 - per-story isolation.
        log.warning("extract %s: image download failed: %s", label, exc)
        return {"status": "error", "error": str(exc)}

    try:
        ocr_text = _vision_ocr(image)
    except Exception as exc:  # noqa: BLE001 - per-story isolation.
        log.warning("extract %s: Vision OCR failed: %s", label, exc)
        return {"status": "error", "error": str(exc)}

    if not ocr_text.strip():
        payload = {
            "status": "no_text",
            "story_id": story_id,
            "handle": handle,
            "extracted_at": _utc_now(),
        }
        log.info("extract %s: no_text", label)
        return _persist_terminal_cache(story_id, payload)

    try:
        result = _gemini_extract(raw, meta, ocr_text)
    except Exception as exc:  # noqa: BLE001 - per-story isolation.
        log.warning("extract %s: Gemini extraction failed: %s", label, exc)
        return {"status": "error", "error": str(exc)}

    status = "ok" if result.get("is_event") else "not_event"
    durable_image_url = _upload_story_flyer(raw, image) if status == "ok" else None
    payload = {
        "status": status,
        "story_id": story_id,
        "handle": handle,
        "ocr_text": ocr_text,
        "result": result,
        "extracted_at": _utc_now(),
    }
    if durable_image_url:
        payload["image_url"] = durable_image_url
    log.info("extract %s: %s", label, status)
    return _persist_terminal_cache(story_id, payload)


def _clean_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        tag = str(item).strip()
        if tag:
            out.append(tag)
    return out


def _category(value: Any) -> str:
    if isinstance(value, str) and value in EVENT_CATEGORIES:
        return value
    return "community"


def _bool_or_default(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
        return default
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
    return default


def _normalize_timestamptz(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat()


def _posted_year(raw: dict[str, Any]) -> int | None:
    posted_at = raw.get("posted_at")
    if not isinstance(posted_at, str):
        return None
    text = posted_at.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text).year
    except ValueError:
        return None


def _distinct_ocr_dates(ocr_text: str) -> set[tuple[int, int]]:
    return {
        (_MONTHS[match.group(1).lower().rstrip(".")], int(match.group(2)))
        for match in _OCR_DATE_RE.finditer(ocr_text)
    }


def _ocr_date(ocr_text: str) -> tuple[int, int] | None:
    dates = _distinct_ocr_dates(ocr_text)
    if len(dates) != 1:
        return None
    return next(iter(dates))


def _parse_ampm_time(
    hour: str,
    minute: str | None,
    meridiem: str,
) -> tuple[int, int] | None:
    hour_value = int(hour)
    minute_value = int(minute or "0")
    if not 1 <= hour_value <= 12 or not 0 <= minute_value <= 59:
        return None

    normalized = meridiem.lower().replace(".", "")
    if normalized == "am":
        hour_value = 0 if hour_value == 12 else hour_value
    elif normalized == "pm":
        hour_value = hour_value if hour_value == 12 else hour_value + 12
    else:
        return None
    return hour_value, minute_value


def _ocr_time_range(ocr_text: str) -> tuple[tuple[int, int], tuple[int, int]] | None:
    full_matches = list(_OCR_TIME_RANGE_RE.finditer(ocr_text))
    compact_matches = list(_OCR_COMPACT_TIME_RANGE_RE.finditer(ocr_text))
    if len(full_matches) + len(compact_matches) != 1:
        return None

    if full_matches:
        match = full_matches[0]
        start = _parse_ampm_time(match.group(1), match.group(2), match.group(3))
        end = _parse_ampm_time(match.group(4), match.group(5), match.group(6))
    else:
        match = compact_matches[0]
        start = _parse_ampm_time(match.group(1), match.group(2), match.group(5))
        end = _parse_ampm_time(match.group(3), match.group(4), match.group(5))
    if start is None or end is None:
        return None
    return start, end


def _ocr_local_event_range(
    raw: dict[str, Any],
    cached: dict[str, Any],
) -> tuple[str, str] | None:
    ocr_text = cached.get("ocr_text")
    if not isinstance(ocr_text, str):
        return None

    year = _posted_year(raw)
    date_parts = _ocr_date(ocr_text)
    time_range = _ocr_time_range(ocr_text)
    if year is None or date_parts is None or time_range is None:
        return None

    month, day = date_parts
    (start_hour, start_minute), (end_hour, end_minute) = time_range
    try:
        start = datetime(
            year,
            month,
            day,
            start_hour,
            start_minute,
            tzinfo=PACIFIC_TZ,
        )
        end = datetime(year, month, day, end_hour, end_minute, tzinfo=PACIFIC_TZ)
    except ValueError:
        return None

    if end <= start:
        return None
    return start.astimezone(timezone.utc).isoformat(), end.astimezone(
        timezone.utc
    ).isoformat()


# Schedule-grid flyers (finals week, welcome week) lay out one column per day,
# and the single-event extractor collapses the whole grid into one event that
# spans the first column to the last — often anchored on an empty day. A real
# event names one or two dates, never a calendar of them, so treat "many dates
# plus a multi-day span" as a mis-collapsed grid and skip it.
_GRID_MIN_DISTINCT_DATES = 3


def _looks_like_schedule_grid(
    ocr_text: Any,
    starts_at: str,
    ends_at: str | None,
) -> bool:
    if not isinstance(ocr_text, str) or not ends_at:
        return False
    if len(_distinct_ocr_dates(ocr_text)) < _GRID_MIN_DISTINCT_DATES:
        return False
    span = datetime.fromisoformat(ends_at) - datetime.fromisoformat(starts_at)
    return span > timedelta(days=1)


def _instagram_event_id(handle: str, starts_at: str) -> str | None:
    if not handle:
        return None
    try:
        start_slug = datetime.fromisoformat(starts_at).strftime("%Y%m%dT%H%MZ")
    except ValueError:
        return None
    return f"ig_{handle}_{start_slug}"


def _to_event_row(
    raw: dict[str, Any],
    cached: dict[str, Any],
    account_meta: dict[str, Any],
    scraped_at: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Return the event row plus the prior event ID it supersedes, if any.

    The superseded ID (derived from the LLM's pre-OCR timestamp) is surfaced
    out-of-band so the row stays a clean DB record; the caller uses it to delete
    the stale row when OCR refines the start time into a new ID.
    """
    if cached.get("status") != "ok":
        return None, None
    llm = cached.get("result") or {}
    if not isinstance(llm, dict) or not llm.get("is_event"):
        return None, None

    title = str(llm.get("title") or "").strip()
    description = str(llm.get("description") or "")
    tags = _clean_tags(llm.get("tags"))
    ocr_range = _ocr_local_event_range(raw, cached)
    llm_starts_at = _normalize_timestamptz(llm.get("starts_at"))
    llm_ends_at = _normalize_timestamptz(llm.get("ends_at"))
    if ocr_range is None:
        starts_at = llm_starts_at
        ends_at = llm_ends_at
    else:
        starts_at, ends_at = ocr_range
    if not title or not starts_at:
        return None, None

    if _looks_like_schedule_grid(cached.get("ocr_text"), starts_at, ends_at):
        log.info(
            "extract %s: skipping collapsed multi-day schedule grid (%s -> %s)",
            raw.get("id"),
            starts_at,
            ends_at,
        )
        return None, None

    handle = str(raw.get("handle") or "")
    rsvp_url = _normalize_url(llm.get("rsvp_url") or raw.get("story_cta_url"))

    # Accounts that asked not to be named publicly on scraped listings.
    if handle in _ANONYMIZED_HOST_HANDLES:
        host = ""
        host_handle = None
    else:
        host = account_meta.get("label") or handle
        host_handle = handle

    # Derive the event ID from (handle, starts_at) so multiple stories about
    # the same event (announcement flyer + "happening now" reminder) collapse
    # into one row via upsert instead of becoming separate events.
    event_id = _instagram_event_id(handle, starts_at)
    if event_id is None:
        return None, None

    row = {
        "id": event_id,
        "title": title[:200],
        "description": description,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "location": str(llm.get("location") or "").strip() or "UC Riverside",
        "host": host,
        "host_handle": host_handle,
        "category": _category(llm.get("category")),
        "content_kind": classify_content_kind(
            "instagram",
            title=title,
            description=description,
            tags=tags,
        ),
        "tags": tags,
        "source": "instagram",
        "source_url": _normalize_url(raw.get("permalink")),
        "image_url": _normalize_url(cached.get("image_url") or raw.get("image_url")),
        "is_free": _bool_or_default(llm.get("is_free"), True),
        "has_free_food": detect_free_food(
            cached.get("ocr_text"), title, description, *tags
        ),
        "rsvp_required": _bool_or_default(llm.get("rsvp_required"), False),
        "rsvp_url": rsvp_url,
        "scraped_at": scraped_at,
    }

    superseded_event_id = (
        _instagram_event_id(handle, llm_starts_at) if llm_starts_at else None
    )
    if superseded_event_id == event_id:
        superseded_event_id = None
    return row, superseded_event_id


def _collect_event_rows(
    meta_by_handle: dict[str, dict[str, Any]],
    scraped_at: str,
) -> tuple[list[dict[str, Any]], set[str]]:
    rows: list[dict[str, Any]] = []
    superseded_ids: set[str] = set()
    for raw in _iter_raw_stories(set(meta_by_handle.keys())):
        story_id = str(raw.get("id") or "")
        if not story_id:
            continue
        cache = _cache_path(story_id)
        if not cache.exists():
            continue
        try:
            cached = _read_json(cache)
        except json.JSONDecodeError:
            log.warning("skipping malformed extraction cache: %s", cache)
            continue
        row, superseded_id = _to_event_row(
            raw,
            cached,
            meta_by_handle.get(str(raw.get("handle") or ""), {}),
            scraped_at,
        )
        if row is not None:
            rows.append(row)
        if superseded_id is not None:
            superseded_ids.add(superseded_id)
    return rows, superseded_ids


def _filter_locked_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    # Query locked events from Supabase to prevent overwriting manual corrections
    try:
        from db import client
        db_client = client()
        locked_res = db_client.table("events").select("id").eq("is_locked", True).execute()
        locked_ids = {row["id"] for row in getattr(locked_res, "data", []) or []}
        if locked_ids:
            log.info("Found %d manually locked events in database. Excluding from story crawler run.", len(locked_ids))
            rows = suppress_tombstoned_event_groups(rows, locked_ids)
    except Exception as e:
        log.warning("Could not fetch locked events for story exclusion: %s. Proceeding with all events.", e)

    return rows


def _filter_deleted_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    from db import get_deleted_event_ids

    deleted_ids = get_deleted_event_ids()
    if deleted_ids:
        log.info(
            "Found %d admin-deleted events. Excluding from story crawler run.",
            len(deleted_ids),
        )
        rows = suppress_tombstoned_event_groups(rows, deleted_ids)
    return rows


def _upsert_events(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    from db import upsert_batched
    return upsert_batched("events", rows)


def _delete_imported_event_ids(ids: set[str]) -> int:
    if not ids:
        return 0

    from db import delete_rows_by_ids

    return delete_rows_by_ids("events", sorted(ids))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ensure_dirs()
    meta_by_handle = _load_account_meta()

    for raw in _iter_raw_stories(set(meta_by_handle.keys())):
        _process_story(raw, meta_by_handle.get(str(raw.get("handle") or ""), {}))

    scraped_at = _utc_now()
    rows, superseded_ids = _collect_event_rows(meta_by_handle, scraped_at)
    current_ids = {row["id"] for row in rows} | superseded_ids
    event_rows = _filter_locked_events(rows)
    event_rows = _filter_deleted_events(event_rows)
    event_rows = dedupe_event_rows(event_rows)
    deleted = _delete_imported_event_ids(
        current_ids - {row["id"] for row in event_rows}
    )
    if deleted:
        log.info("Deleted %d stale Instagram event rows from Supabase", deleted)
    written = _upsert_events(event_rows)
    log.info("Wrote %d events to Supabase", written)
    notified = notify_free_food_events(event_rows)
    if notified:
        log.info("Sent %d free food Discord notifications", notified)


if __name__ == "__main__":
    main()
