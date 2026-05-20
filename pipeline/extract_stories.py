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
from urllib.parse import urlsplit

from config import (
    EXTRACTED_DIR,
    GEMINI_API_KEY,
    GOOGLE_VISION_API_KEY,
    RAW_DIR,
    ensure_dirs,
    load_accounts,
)

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
        "year from posted_at when a date omits the year. Return starts_at and "
        "ends_at as ISO-8601 timestamps with timezone offsets. Prefer exact "
        "text from OCR over guessing.\n\n"
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
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is required for Gemini extraction")

    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)
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

    if raw.get("is_video"):
        log.info("extract %s: skipped_video", label)
        return {"status": "skipped_video"}

    cache = _cache_path(story_id)
    if cache.exists():
        cached = _read_json(cache)
        log.info("extract %s: cache %s", label, cached.get("status"))
        return cached

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
        return _write_cache(story_id, payload)
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
        return _write_cache(story_id, payload)

    try:
        result = _gemini_extract(raw, meta, ocr_text)
    except Exception as exc:  # noqa: BLE001 - per-story isolation.
        log.warning("extract %s: Gemini extraction failed: %s", label, exc)
        return {"status": "error", "error": str(exc)}

    status = "ok" if result.get("is_event") else "not_event"
    payload = {
        "status": status,
        "story_id": story_id,
        "handle": handle,
        "ocr_text": ocr_text,
        "result": result,
        "extracted_at": _utc_now(),
    }
    log.info("extract %s: %s", label, status)
    return _write_cache(story_id, payload)


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


_URL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+\-.]*:", re.IGNORECASE)


def _normalize_url(value: Any) -> str | None:
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
    return text


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
    starts_at = _normalize_timestamptz(llm.get("starts_at"))
    if not title or not starts_at:
        return None
    ends_at = _normalize_timestamptz(llm.get("ends_at"))

    handle = str(raw.get("handle") or "")
    rsvp_url = _normalize_url(llm.get("rsvp_url") or raw.get("story_cta_url"))

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
        "host": account_meta.get("label") or handle,
        "host_handle": handle,
        "category": _category(llm.get("category")),
        "tags": _clean_tags(llm.get("tags")),
        "source": "instagram",
        "source_url": _normalize_url(raw.get("permalink")),
        "image_url": _normalize_url(raw.get("image_url")),
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
    written = _upsert_events(list(by_id.values()))
    log.info("Wrote %d events to Supabase", written)


if __name__ == "__main__":
    main()
