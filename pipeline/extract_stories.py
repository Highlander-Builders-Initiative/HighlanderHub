"""Extract structured events from raw Instagram story image flyers.

Reads raw story JSON from data/raw/<handle>/, runs OCR + Gemini extraction for
uncached image stories, caches terminal results in data/extracted/, then writes
event-shaped rows to Supabase.

Date and time reasoning over flyer text lives in `story_dates`; this module
assembles rows and owns caching, extraction and publishing.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from config import (
    EXTRACTED_DIR,
    GOOGLE_CLOUD_LOCATION,
    GOOGLE_CLOUD_PROJECT,
    GOOGLE_VISION_API_KEY,
    RAW_DIR,
    ensure_dirs,
    load_accounts,
)
from classify import classify_content_kind, detect_free_food, is_informational_notice
from discord_notify import notify_free_food_events
from event_identity import dedupe_event_rows, suppress_tombstoned_event_groups
from flyer_qr import QR_SCAN_VERSION, qr_rsvp_urls
from reshare import reshared_origin_handle, strip_byline
from story_dates import (
    align_printed_dates,
    has_source_date,
    immediate_event_range,
    is_single_session_reminder,
    local_event_range,
    looks_like_schedule_grid,
    midnight_end,
    normalize_timestamptz,
    was_stale_when_posted,
)
from url_utils import normalize_http_url as _normalize_url
from url_utils import normalize_rsvp_url

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
    temporary = path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    temporary.replace(path)
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
    if status not in REMOTE_CACHE_TERMINAL_STATUSES | {"error"}:
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


def _persist_error(raw: dict[str, Any], stage: str, exc: Exception) -> dict[str, Any]:
    """Keep retryable failures inspectable locally and in the remote result JSON."""
    payload = {
        "status": "error", "story_id": str(raw.get("id") or ""),
        "handle": raw.get("handle"), "extracted_at": _utc_now(),
        "result": {"stage": stage, "error": f"{type(exc).__name__}: {exc}"},
    }
    return _persist_terminal_cache(payload["story_id"], payload)


def _load_account_meta() -> dict[str, dict[str, Any]]:
    return {a["handle"]: a for a in load_accounts()}


@lru_cache(maxsize=1)
def _known_handles() -> frozenset[str]:
    """The crawl roster, used to tell a reshare byline from flyer prose."""
    try:
        return frozenset(_load_account_meta())
    except Exception as exc:  # noqa: BLE001 - byline detection degrades gracefully.
        log.warning("reshare: account roster unavailable: %s", exc)
        return frozenset()


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
    if resp.status_code in {404, 410}:
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
    known_handles: Iterable[str] = (),
) -> str:
    context = {
        "ocr_text": ocr_text,
        "instagram_handle": raw.get("handle"),
        "reshared_from": _reshared_owner(raw) or reshared_origin_handle(
            ocr_text, str(raw.get("handle") or ""), known_handles
        ),
        # The story renders a truncated caption; this is the full text when
        # the scraper could reach the attached post.
        "reshared_post_caption": (raw.get("reshared_post") or {}).get("caption")
        if isinstance(raw.get("reshared_post"), dict)
        else None,
        "account_label": meta.get("label"),
        "account_category": meta.get("category"),
        "story_caption": raw.get("caption"),
        "story_cta_url": raw.get("story_cta_url"),
        "posted_at": raw.get("posted_at"),
        "category_values": list(LLM_EVENT_CATEGORIES),
    }
    return (
        "Extract a UC Riverside campus event from this Instagram story flyer. "
        "Return JSON only. When reshared_from is set the story reshares that "
        "account's post, so the OCR begins with Instagram's byline and a "
        "caption line prefixed by a handle. Those are app chrome: never use a "
        "handle or a byline like 'a and b' as the title. Prefer "
        "reshared_post_caption when it is present, since the story renders "
        "that caption truncated; otherwise title the event from the caption "
        "wording that is visible. "
        "If the flyer is not advertising a specific event, "
        "set is_event to false and keep title and starts_at null. Informational "
        "tips, officer introductions, and seasonal spotlights are not events. "
        "Require a date in OCR or the story caption, including an explicit "
        "relative date such as tomorrow. Never use posted_at as the event date "
        "when source text supplies no date; keep starts_at and ends_at null. Infer the "
        "year from posted_at when a date omits the year. "
        "A numeric layout explicitly labeled MONTH DAY YEAR gives those values "
        "in that order; 11 07 26 means November 7, 2026. Dotted dates such as "
        "10.31 beside an event clock mean October 31. Awareness observances, "
        "resource reminders, and service closures are not gatherings. "
        "UCR is in Riverside, California, so interpret flyer times as America/Los_Angeles local "
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
        contents=_build_gemini_prompt(raw, meta, ocr_text, _known_handles()),
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


def _add_qr_result(cached: dict[str, Any], image: bytes) -> dict[str, Any]:
    result = cached.get("result")
    if (cached.get("status") != "ok" or not isinstance(result, dict)
            or not result.get("rsvp_required")
            or result.get("_qr_scan_version") == QR_SCAN_VERSION):
        return cached
    try:
        urls = qr_rsvp_urls(image)
    except Exception as exc:  # noqa: BLE001 - QR recovery must not lose an event.
        log.warning("extract %s: QR decoding failed: %s", cached.get("story_id"), exc)
        return cached
    # The result JSON survives both local and remote cache round trips.
    return {**cached, "result": {
        **result, "_qr_scan_version": QR_SCAN_VERSION, "_qr_urls": urls,
    }}


def _repair_cached_rsvp(raw: dict[str, Any], cached: dict[str, Any]) -> dict[str, Any]:
    result = cached.get("result")
    if (cached.get("status") != "ok" or not isinstance(result, dict)
            or not result.get("rsvp_required")
            or result.get("_qr_scan_version") == QR_SCAN_VERSION):
        return cached
    row, _ = _to_event_row(raw, cached, {}, _utc_now(), _known_handles())
    if row is None or datetime.fromisoformat(row["ends_at"] or row["starts_at"]) <= datetime.fromisoformat(_utc_now()):
        return cached
    try:
        image = _download_image(cached.get("image_url") or raw.get("image_url"))
    except Exception as exc:  # noqa: BLE001 - retry transient failures next run.
        log.warning("extract %s: QR flyer download failed: %s", raw.get("id"), exc)
        return cached
    repaired = _add_qr_result(cached, image)
    if repaired == cached:
        return cached
    return _persist_terminal_cache(str(raw["id"]), repaired)


def _repair_cached_flyer(
    raw: dict[str, Any], cached: dict[str, Any]
) -> dict[str, Any]:
    """Retry a missing upload without repeating successful OCR or extraction."""
    if (
        cached.get("status") != "ok"
        or cached.get("image_url")
        or not raw.get("image_url")
    ):
        return cached
    result = cached.get("result")
    if isinstance(result, dict):
        starts_at, ends_at = local_event_range(raw, cached) or (
            normalize_timestamptz(result.get("starts_at")),
            normalize_timestamptz(result.get("ends_at")),
        )
        if starts_at:
            ends_at = midnight_end(cached.get("ocr_text"), starts_at, ends_at)
        # Match event-row handling of invalid ends and OCR-corrected dates.
        if starts_at and ends_at and datetime.fromisoformat(ends_at) <= datetime.fromisoformat(starts_at):
            ends_at = None
        latest_event_time = ends_at or starts_at
        if (
            latest_event_time
            and datetime.fromisoformat(latest_event_time) <= datetime.fromisoformat(_utc_now())
        ):
            return cached
    try:
        image = _download_image(raw["image_url"])
    except Exception as exc:  # noqa: BLE001 - preserve the usable extraction.
        log.warning("extract %s: flyer recovery download failed: %s", raw.get("id"), exc)
        return cached
    image_url = _upload_story_flyer(raw, image)
    if not image_url:
        return cached
    repaired = _add_qr_result({**cached, "image_url": image_url}, image)
    return _persist_terminal_cache(str(raw["id"]), repaired)


def _process_story(raw: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    story_id = str(raw.get("id") or "")
    handle = str(raw.get("handle") or "")
    label = f"ig_{handle}_{story_id}" if handle and story_id else story_id or "unknown"

    if not story_id:
        log.warning("extract %s: missing story id", label)
        return {"status": "error", "error": "missing story id"}

    reshared = _reshared_media_identity(raw)
    if reshared:
        # The feed post is collected and assessed on its own. Re-reading the
        # story embed would duplicate OCR, a model call, and a second source.
        log.info("extract %s: skipped reshare of %s", label, reshared)
        return {
            "status": "skipped_reshare",
            "story_id": story_id,
            "handle": handle,
            "reshared_media": reshared,
            "extracted_at": _utc_now(),
        }

    cache = _cache_path(story_id)
    if cache.exists():
        try:
            cached = _read_json(cache)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            log.warning("extract %s: unreadable cache: %s", label, exc)
        else:
            if (
                isinstance(cached, dict)
                and cached.get("status") in REMOTE_CACHE_TERMINAL_STATUSES
            ):
                log.debug("extract %s: cache %s", label, cached.get("status"))
                return _repair_cached_rsvp(raw, _repair_cached_flyer(raw, cached))
            log.warning("extract %s: invalid cache payload; retrying", label)

    remote_cached = _load_remote_cache(story_id)
    if (
        remote_cached is not None
        and remote_cached.get("status") in REMOTE_CACHE_TERMINAL_STATUSES
    ):
        log.info("extract %s: remote cache %s", label, remote_cached.get("status"))
        return _repair_cached_rsvp(
            raw, _repair_cached_flyer(raw, _write_cache(story_id, remote_cached))
        )

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
        return _persist_error(raw, "download", exc)

    try:
        ocr_text = _vision_ocr(image)
    except Exception as exc:  # noqa: BLE001 - per-story isolation.
        log.warning("extract %s: Vision OCR failed: %s", label, exc)
        return _persist_error(raw, "ocr", exc)

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
        return _persist_error(raw, "gemini", exc)

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
    payload = _add_qr_result(payload, image)
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


def _instagram_event_id(handle: str, starts_at: str) -> str | None:
    if not handle:
        return None
    try:
        start_slug = datetime.fromisoformat(starts_at).strftime("%Y%m%dT%H%MZ")
    except ValueError:
        return None
    return f"ig_{handle}_{start_slug}"


def _reshared_owner(raw: dict[str, Any]) -> str | None:
    """The post author recorded by the scraper, if the story reshares a post.

    Authoritative when present — it comes from the story payload rather than
    from reading a byline off the rendered image — but only newer stories
    carry it, so callers fall back to the OCR byline.
    """
    post = raw.get("reshared_post")
    if not isinstance(post, dict):
        return None
    owner = str(post.get("owner_username") or "").strip().lower()
    return owner or None


def _reshared_media_identity(raw: dict[str, Any]) -> str | None:
    post = raw.get("reshared_post")
    media_id = str(post.get("media_id") or "") if isinstance(post, dict) else ""
    return f"post_{media_id}" if re.fullmatch(r"\d+", media_id) else None


def _caption_fallback_title(description: str) -> str:
    """Name an event whose flyer text was only reshare chrome.

    A reshared photo post shows a truncated caption and nothing else, so there
    is no printed title to read. The caption's opening clause is the closest
    thing to one, and beats showing a bare Instagram handle.
    """
    opening = re.split(r"(?<=[.!?])\s|\s[-–—]\s|\n", description.strip(), maxsplit=1)
    candidate = opening[0].strip() if opening else ""
    candidate = candidate.rstrip(" .…").strip()
    return candidate[:120] if len(candidate) >= 8 else ""


def _to_event_row(
    raw: dict[str, Any],
    cached: dict[str, Any],
    account_meta: dict[str, Any],
    scraped_at: str,
    known_handles: Iterable[str] = (),
    *,
    assessed_kind: str | None = None,
) -> tuple[dict[str, Any] | None, set[str]]:
    """Return the event row plus any prior event IDs to retire.

    Superseded IDs are surfaced out-of-band so the row stays a clean DB record;
    the caller uses them to delete stale rows when OCR refines the start time
    into a new ID, when source text provides no date, or when the story turns
    out to reshare another account's post and the event re-keys onto that
    account. The caller retains IDs supported by another valid story.
    """
    if cached.get("status") != "ok":
        return None, set()
    llm = cached.get("result") or {}
    if not isinstance(llm, dict) or not llm.get("is_event"):
        return None, set()

    description = str(llm.get("description") or "")
    tags = _clean_tags(llm.get("tags"))
    ocr_range = local_event_range(raw, cached)
    llm_starts_at = normalize_timestamptz(llm.get("starts_at"))
    llm_ends_at = normalize_timestamptz(llm.get("ends_at"))

    # A reshared post carries the original author's byline, which the LLM
    # reads as body text. Keep it out of the title, and key the event on the
    # original author so every club that reshares one post lands on one row.
    ocr_text = cached.get("ocr_text")
    origin_handle = _reshared_owner(raw) or reshared_origin_handle(
        ocr_text, str(raw.get("handle") or ""), known_handles
    )
    handle = str(raw.get("handle") or "")
    media_identity = _reshared_media_identity(raw)
    identity_handle = origin_handle or media_identity or handle
    legacy_range = immediate_event_range(
        raw, cached, llm_starts_at, llm_ends_at, legacy=True
    )
    prior_starts = {
        llm_starts_at,
        ocr_range[0] if ocr_range else None,
        legacy_range[0] if legacy_range else None,
    }
    identity_accounts = {handle, origin_handle, media_identity}
    prior_ids = {
        event_id
        for account in identity_accounts if account
        for start in prior_starts if start
        if (event_id := _instagram_event_id(account, start))
    }
    title = strip_byline(
        str(llm.get("title") or ""),
        ocr_text,
        str(raw.get("handle") or ""),
        known_handles,
    )
    if not title:
        # The card showed only chrome and a truncated caption, so the LLM had
        # no real title to find. The caption still names the event usefully.
        title = _caption_fallback_title(description)

    if assessed_kind is None and is_informational_notice(title, description, str(ocr_text or "")):
        log.info("extract %s: skipping informational notice", raw.get("id"))
        return None, prior_ids
    if assessed_kind is None and not has_source_date(raw, cached):
        log.info("extract %s: skipping event without a source date", raw.get("id"))
        return None, prior_ids
    if assessed_kind is not None:
        starts_at, ends_at = llm_starts_at, llm_ends_at
    elif ocr_range is not None:
        starts_at, ends_at = ocr_range
    else:
        starts_at, ends_at = immediate_event_range(
            raw, cached, llm_starts_at, llm_ends_at
        ) or (llm_starts_at, llm_ends_at)
    if not title or not starts_at:
        return None, set()

    supported_range = (
        (starts_at, ends_at) if assessed_kind is not None or is_single_session_reminder(raw, cached, starts_at, ends_at)
        else align_printed_dates(raw, cached, starts_at, ends_at)
    )
    if supported_range is None:
        log.info("extract %s: skipping date unsupported by source", raw.get("id"))
        return None, prior_ids
    starts_at, ends_at = supported_range

    ends_at = midnight_end(ocr_text, starts_at, ends_at)
    if ends_at and datetime.fromisoformat(ends_at) <= datetime.fromisoformat(starts_at):
        log.info(
            "extract %s: dropping invalid end time (%s <= %s)",
            raw.get("id"),
            ends_at,
            starts_at,
        )
        ends_at = None

    if (assessed_kind is None and looks_like_schedule_grid(cached.get("ocr_text"), starts_at, ends_at)
            and not is_single_session_reminder(raw, cached, starts_at, ends_at)):
        log.info(
            "extract %s: skipping ambiguous multi-event schedule (%s -> %s)",
            raw.get("id"),
            starts_at,
            ends_at,
        )
        return None, prior_ids

    if was_stale_when_posted(raw, starts_at, ends_at):
        log.info(
            "extract %s: skipping event already stale when story was posted (%s)",
            raw.get("id"),
            starts_at,
        )
        return None, prior_ids

    qr_values = llm.get("_qr_urls")
    qr_urls = {url for value in (qr_values if isinstance(qr_values, list) else [])
               if (url := normalize_rsvp_url(value))}
    rsvp_url = (
        normalize_rsvp_url(raw.get("story_cta_url"))
        or (next(iter(qr_urls)) if len(qr_urls) == 1 else None)
        or normalize_rsvp_url(llm.get("rsvp_url"), str(ocr_text or ""))
    )

    # Accounts that asked not to be named publicly on scraped listings.
    if handle in _ANONYMIZED_HOST_HANDLES or origin_handle in _ANONYMIZED_HOST_HANDLES:
        host = ""
        host_handle = None
    elif origin_handle and origin_handle != handle:
        origin_meta = known_handles.get(origin_handle, {}) if isinstance(known_handles, dict) else {}
        host = origin_meta.get("label") or origin_handle
        host_handle = origin_handle
    else:
        host = account_meta.get("label") or handle
        host_handle = handle

    # Derive the event ID from (handle, starts_at) so multiple stories about
    # the same event (announcement flyer + "happening now" reminder) collapse
    # into one row via upsert instead of becoming separate events. For a
    # reshare the identity account is whoever wrote the post, not whoever
    # reshared it, so every club amplifying one post collapses too.
    event_id = _instagram_event_id(identity_handle, starts_at)
    if event_id is None:
        return None, set()

    row = {
        "id": event_id,
        "title": title[:200],
        "description": description,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "location": str(llm.get("location") or "").strip() or ("UC Riverside" if assessed_kind is None else ""),
        "host": host,
        "host_handle": host_handle,
        "category": _category(llm.get("category")),
        "content_kind": classify_content_kind(
            "instagram",
            title=title,
            description=description,
            tags=tags,
            ocr_text=str(cached.get("ocr_text") or ""),
            assessed_kind=assessed_kind,
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

    # Retire IDs this story would have produced under an earlier reading:
    # the LLM's pre-OCR start time, and — when the story turns out to be a
    # reshare — the crawled account's own ID, which is where the duplicate
    # rows live today.
    superseded_ids = prior_ids | {
        candidate
        for account in identity_accounts
        for start in {starts_at}
        if account and start
        if (candidate := _instagram_event_id(account, start))
    }
    superseded_ids.discard(event_id)
    return row, superseded_ids


def _collect_event_rows(
    processed: list[tuple[dict[str, Any], dict[str, Any]]],
    meta_by_handle: dict[str, dict[str, Any]],
    scraped_at: str,
) -> tuple[list[dict[str, Any]], set[str], dict[str, set[str]]]:
    """Build event rows from the (raw, extraction) pairs produced this run.

    Also returns, per surviving row, the IDs that row replaced, so an admin's
    delete or lock on the older ID still binds after an event re-keys.

    Works off the in-memory results from _process_story instead of re-reading
    the raw archive and extraction cache from disk. _to_event_row already drops
    anything whose status isn't a usable "ok" event.
    """
    rows: list[dict[str, Any]] = []
    superseded_ids: set[str] = set()
    retired_by: dict[str, set[str]] = {}
    known_handles = meta_by_handle
    # Share an observed author across copies of the same attached post. When
    # no copy identifies the author, every copy uses the stable media ID.
    owners_by_media: dict[str, set[str]] = {}
    for raw, cached in processed:
        media = _reshared_media_identity(raw)
        owner = _reshared_owner(raw) or reshared_origin_handle(
            cached.get("ocr_text"), str(raw.get("handle") or ""), known_handles
        )
        if media and owner:
            owners_by_media.setdefault(media, set()).add(owner)
    for raw, cached in processed:
        owners = owners_by_media.get(_reshared_media_identity(raw), set())
        if len(owners) == 1 and not _reshared_owner(raw):
            raw = {**raw, "reshared_post": {
                **raw["reshared_post"], "owner_username": next(iter(owners)),
            }}
        row, story_superseded_ids = _to_event_row(
            raw,
            cached,
            meta_by_handle.get(str(raw.get("handle") or ""), {}),
            scraped_at,
            known_handles,
        )
        if row is not None:
            rows.append(row)
            retired_by.setdefault(row["id"], set()).update(story_superseded_ids)
        superseded_ids |= story_superseded_ids
    return rows, superseded_ids, retired_by


def _inherit_tombstones(
    tombstoned_ids: set[str],
    retired_by: dict[str, set[str]],
) -> set[str]:
    """Extend a tombstone set onto rows that replaced a tombstoned ID.

    An admin who deleted or locked an event before it re-keyed (a reshare
    moving onto the original author, or OCR refining the start time) expects
    that decision to stick, so the successor row inherits it.
    """
    return tombstoned_ids | {
        row_id
        for row_id, replaced_ids in retired_by.items()
        if replaced_ids & tombstoned_ids
    }


def _filter_locked_events(
    rows: list[dict[str, Any]],
    retired_by: dict[str, set[str]] | None = None,
) -> list[dict[str, Any]]:
    if not rows:
        return []

    # Query locked events from Supabase to prevent overwriting manual corrections
    try:
        from db import client
        db_client = client()
        locked_res = db_client.table("events").select("id").eq("is_locked", True).execute()
        locked_ids = {row["id"] for row in getattr(locked_res, "data", []) or []}
        locked_ids = _inherit_tombstones(locked_ids, retired_by or {})
        if locked_ids:
            log.info("Found %d manually locked events in database. Excluding from story crawler run.", len(locked_ids))
            rows = suppress_tombstoned_event_groups(rows, locked_ids)
    except Exception as e:
        log.warning("Could not fetch locked events for story exclusion: %s. Proceeding with all events.", e)

    return rows


def _filter_deleted_events(
    rows: list[dict[str, Any]],
    retired_by: dict[str, set[str]] | None = None,
) -> list[dict[str, Any]]:
    if not rows:
        return []

    from db import get_deleted_event_ids

    deleted_ids = _inherit_tombstones(get_deleted_event_ids(), retired_by or {})
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

    from db import delete_unlocked_event_rows_by_ids

    return delete_unlocked_event_rows_by_ids(sorted(ids))


def extract_all(
    meta_by_handle: dict[str, dict[str, Any]] | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Read every archived story once, returning (raw, extraction) pairs.

    Kept separate from publication so the runner can extract both Instagram
    channels before settling their shared event support in one transaction.
    """
    ensure_dirs()
    meta_by_handle = _load_account_meta() if meta_by_handle is None else meta_by_handle
    processed: list[tuple[dict[str, Any], dict[str, Any]]] = []
    cache_hits = 0
    for raw in _iter_raw_stories(set(meta_by_handle.keys())):
        story_id = str(raw.get("id") or "")
        if story_id and _cache_path(story_id).exists():
            cache_hits += 1
        cached = _process_story(raw, meta_by_handle.get(str(raw.get("handle") or ""), {}))
        processed.append((raw, cached))
    log.info(
        "extract: %d stories (%d cached, %d newly processed)",
        len(processed),
        cache_hits,
        len(processed) - cache_hits,
    )
    return processed


def main(*, notify: bool = True) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    meta_by_handle = _load_account_meta()
    processed = extract_all(meta_by_handle)
    from assessed_events import publish_stories
    publish_stories(processed, meta_by_handle, _utc_now(), notify=notify)


if __name__ == "__main__":
    main()
