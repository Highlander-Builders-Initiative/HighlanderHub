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
from datetime import datetime, timezone
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
from discord_notify import notify_free_food_events
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
    r"\s*(?:-|to)?\s+"
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
        "category": {"type": "string", "enum": list(EVENT_CATEGORIES)},
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
        "category_values": list(EVENT_CATEGORIES),
    }
    return (
        "Extract a UC Riverside campus event from this Instagram story flyer. "
        "Return JSON only. If the flyer is not advertising a specific event, "
        "set is_event to false and keep title and starts_at null. Infer the "
        "year from posted_at when a date omits the year. UCR is in Riverside, "
        "California, so interpret flyer times as America/Los_Angeles local "
        "wall time unless the OCR explicitly gives another timezone. Do not "
        "change an explicit OCR date based on relative text like THIS SUNDAY "
        "or NEXT SUNDAY. For ranges like 11:00 AM 2:00 PM, use 11:00 AM as "
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


def _ocr_date(ocr_text: str) -> tuple[int, int] | None:
    dates = {
        (_MONTHS[match.group(1).lower().rstrip(".")], int(match.group(2)))
        for match in _OCR_DATE_RE.finditer(ocr_text)
    }
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
    matches = list(_OCR_TIME_RANGE_RE.finditer(ocr_text))
    if len(matches) != 1:
        return None

    match = matches[0]
    start = _parse_ampm_time(match.group(1), match.group(2), match.group(3))
    end = _parse_ampm_time(match.group(4), match.group(5), match.group(6))
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


def _to_event_row(
    raw: dict[str, Any],
    cached: dict[str, Any],
    account_meta: dict[str, Any],
    scraped_at: str,
) -> dict[str, Any] | None:
    if cached.get("status") != "ok":
        return None
    llm = cached.get("result") or {}
    if not isinstance(llm, dict) or not llm.get("is_event"):
        return None

    title = str(llm.get("title") or "").strip()
    ocr_range = _ocr_local_event_range(raw, cached)
    if ocr_range is None:
        starts_at = _normalize_timestamptz(llm.get("starts_at"))
        ends_at = _normalize_timestamptz(llm.get("ends_at"))
    else:
        starts_at, ends_at = ocr_range
    if not title or not starts_at:
        return None

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
    start_slug = datetime.fromisoformat(starts_at).strftime("%Y%m%dT%H%MZ")

    return {
        "id": f"ig_{handle}_{start_slug}",
        "title": title[:200],
        "description": str(llm.get("description") or ""),
        "starts_at": starts_at,
        "ends_at": ends_at,
        "location": str(llm.get("location") or "").strip() or "UC Riverside",
        "host": host,
        "host_handle": host_handle,
        "category": _category(llm.get("category")),
        "tags": _clean_tags(llm.get("tags")),
        "source": "instagram",
        "source_url": _normalize_url(raw.get("permalink")),
        "image_url": _normalize_url(cached.get("image_url") or raw.get("image_url")),
        "is_free": _bool_or_default(llm.get("is_free"), True),
        "rsvp_required": _bool_or_default(llm.get("rsvp_required"), False),
        "rsvp_url": rsvp_url,
        "scraped_at": scraped_at,
    }


def _collect_event_rows(
    meta_by_handle: dict[str, dict[str, Any]],
    scraped_at: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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
        row = _to_event_row(
            raw,
            cached,
            meta_by_handle.get(str(raw.get("handle") or ""), {}),
            scraped_at,
        )
        if row is not None:
            rows.append(row)
    return rows


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
            rows = [r for r in rows if r["id"] not in locked_ids]
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
        rows = [r for r in rows if r["id"] not in deleted_ids]
    return rows


def _upsert_events(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    from db import upsert_batched
    return upsert_batched("events", rows)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ensure_dirs()
    meta_by_handle = _load_account_meta()

    for raw in _iter_raw_stories(set(meta_by_handle.keys())):
        _process_story(raw, meta_by_handle.get(str(raw.get("handle") or ""), {}))

    scraped_at = _utc_now()
    rows = _collect_event_rows(meta_by_handle, scraped_at)
    # Same event often appears in several stories; keep the most informative
    # row per id (the original flyer usually has a longer description than
    # the follow-up reminder).
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        existing = by_id.get(row["id"])
        if existing is None or len(row.get("description") or "") > len(
            existing.get("description") or ""
        ):
            by_id[row["id"]] = row
    event_rows = _filter_locked_events(list(by_id.values()))
    event_rows = _filter_deleted_events(event_rows)
    written = _upsert_events(event_rows)
    log.info("Wrote %d events to Supabase", written)
    notified = notify_free_food_events(event_rows)
    if notified:
        log.info("Sent %d free food Discord notifications", notified)


if __name__ == "__main__":
    main()
