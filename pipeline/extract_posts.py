"""OCR every slide of Instagram feed posts for assessment.

Every slide and the caption supply event details. Each image is
cached under a signature-free media key, so editing a caption reuses its OCR
and a re-signed CDN URL costs nothing at all.

Publication itself lives in `assessed_events`, which reads the caches this
module writes. Nothing here decides whether a post is an event.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from config import POST_EXTRACTED_DIR, ensure_post_dirs, load_accounts
from image_ocr import (
    DURABLE_FLYER_BUCKET,
    ImageExpired,
    _download_image,
    _vision_ocr,
)
from flyer_qr import QR_SCAN_VERSION, qr_rsvp_urls
from post_archive import ArchiveIndex, hydrate_local_posts, iter_local_posts

log = logging.getLogger("pipeline.extract_posts")

# Bump when the meaning of a cached extraction changes — a new media type
# becoming readable, a different OCR engine, a different slide decomposition.
# A bump invalidates post extractions.
EXTRACTION_VERSION = 3

# Retain unsupported_media for reading legacy caches, but reopen those skips:
# carousel length no longer prevents reading every slide.
# A failed post stays retryable and extraction moves on. Stop after this many
# service failures in a row; expired image URLs do not establish an outage.
# expired_media sets aside a post whose saved image URL has expired until that
# URL is refreshed: saved posts are never re-requested, so a retry cannot succeed.
MAX_CONSECUTIVE_FAILURES = 3
TERMINAL_STATUSES = {"ok", "no_text", "unsupported_media", "no_media", "expired_media"}


class Stats(dict):
    """Per-stage counters reported by the runner."""

    def bump(self, key: str, amount: int = 1) -> None:
        self[key] = self.get(key, 0) + amount


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_path(media_id: str) -> Path:
    return POST_EXTRACTED_DIR / f"{media_id}.json"


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def fingerprint(record: dict[str, Any]) -> str:
    """Identify the extraction inputs, excluding expiring URL signatures.

    Caption and publication context are inputs because they are read as event
    evidence; media identity is an input because a replaced slide is new
    evidence. The signed CDN URL is deliberately absent: Instagram re-signs it
    on every fetch, and including it would invalidate every cache daily.
    """
    payload = {
        "version": EXTRACTION_VERSION,
        "caption": record.get("caption") or "",
        "posted_at": record.get("posted_at"),
        "owner_username": record.get("owner_username"),
        "media": [
            [entry.get("media_key"), bool(entry.get("is_video"))]
            for entry in _readable_slides(record)
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _write_cache(media_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    POST_EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(media_id)
    temporary = path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    temporary.replace(path)
    return payload


def _remote_row_to_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    if row.get("status") not in TERMINAL_STATUSES | {"error"}:
        return None
    payload: dict[str, Any] = {
        "status": row["status"],
        "media_id": str(row.get("media_id") or ""),
        "handle": str(row.get("handle") or ""),
        "fingerprint": row.get("fingerprint"),
        "extraction_version": row.get("extraction_version"),
        "images": row.get("images") or [],
        "extracted_at": row.get("extracted_at") or _utc_now(),
    }
    if row.get("caption") is not None:
        payload["caption"] = row["caption"]
    if row.get("result") is not None:
        payload["result"] = row["result"]
    return payload


def _load_remote_cache(media_id: str) -> dict[str, Any] | None:
    try:
        from db import client

        response = (
            client()
            .table("post_extractions")
            .select("media_id,handle,status,fingerprint,extraction_version,caption,images,result,extracted_at")
            .eq("media_id", media_id)
            .maybe_single()
            .execute()
        )
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - remote cache is best-effort.
        log.warning("post_extractions: cache lookup failed for %s: %s", media_id, exc)
        return None
    row = getattr(response, "data", None)
    return _remote_row_to_payload(row) if isinstance(row, dict) else None


def _write_remote_cache(payload: dict[str, Any]) -> None:
    if payload.get("status") not in TERMINAL_STATUSES | {"error"}:
        return
    row = {
        "media_id": payload.get("media_id"),
        "handle": payload.get("handle"),
        "status": payload.get("status"),
        "fingerprint": payload.get("fingerprint"),
        "extraction_version": payload.get("extraction_version"),
        "caption": payload.get("caption"),
        "images": payload.get("images") or [],
        "result": payload.get("result"),
        "extracted_at": payload.get("extracted_at") or _utc_now(),
    }
    if not row["media_id"]:
        return
    try:
        from db import upsert_batched

        upsert_batched("post_extractions", [row], on_conflict="media_id")
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - local cache is authoritative.
        log.warning("post_extractions: cache write failed for %s: %s", row["media_id"], exc)


def _persist(media_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    cached = _write_cache(media_id, payload)
    _write_remote_cache(cached)
    return cached


def known_images(cached: Any) -> dict[str, dict[str, Any]]:
    """Per-slide results from a previous run, keyed by media key.

    Read from error payloads too: a post whose third slide failed to download
    has already paid for the first two, and a retry must not repeat them.
    """
    if not isinstance(cached, dict):
        return {}
    found: dict[str, dict[str, Any]] = {}
    for entry in cached.get("images") or []:
        key = entry.get("media_key") if isinstance(entry, dict) else None
        if isinstance(key, str) and key and entry.get("ocr_text") is not None:
            found[key] = entry
    return found


def _storage_object_path(record: dict[str, Any], media_key: str) -> str | None:
    handle = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(record.get("handle") or "")).strip("._-")
    media_id = re.sub(r"[^A-Za-z0-9_-]+", "", str(record.get("media_id") or ""))
    slug = re.sub(r"[^A-Za-z0-9_-]+", "", media_key)[:64]
    if not handle or not media_id or not slug:
        return None
    return f"instagram/{handle}/posts/{media_id}/{slug}.jpg"


def _upload_flyer(record: dict[str, Any], media_key: str, image: bytes) -> str | None:
    path = _storage_object_path(record, media_key)
    if path is None:
        return None
    try:
        from db import client

        bucket = client().storage.from_(DURABLE_FLYER_BUCKET)
        bucket.upload(
            path,
            image,
            {"content-type": "image/jpeg", "cache-control": "31536000", "upsert": "true"},
        )
        return bucket.get_public_url(path)
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - extraction still succeeds.
        log.warning("post flyer upload failed for %s: %s", path, exc)
        return None


def _readable_slides(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Read every slide, using the cover JPEG for video slides."""
    return [entry for entry in (record.get("media") or []) if isinstance(entry, dict)]


def _url_attempt(url: str) -> str:
    """Identify one signed URL, so an expired one is not requested again."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _cached_decision_still_applies(record: dict[str, Any], payload: Any) -> bool:
    """True when a terminal cache is still the decision for this record.

    Legacy video and long-carousel skips are reopened under all-slide reading.
    An expiry holds only while the slide keeps the URL that expired; the
    fingerprint excludes signatures, so a refreshed URL must reopen it here.
    """
    if not (isinstance(payload, dict) and payload.get("status") in TERMINAL_STATUSES
            and payload.get("fingerprint") == fingerprint(record)):
        return False
    if payload.get("status") == "expired_media":
        result = payload.get("result") or {}
        return any(slide.get("media_key") == result.get("media_key")
                   and _url_attempt(slide.get("image_url") or "") == result.get("expired_url")
                   for slide in _readable_slides(record))
    return payload.get("status") != "unsupported_media"


def _ensure_durable_flyer(record: dict[str, Any], slide: dict[str, Any],
                          entry: dict[str, Any], stats: Stats, *,
                          cached_only: bool, image: bytes | None = None) -> dict[str, Any]:
    """Complete flyer storage independently of OCR, reusing bytes when available."""
    if cached_only or entry.get("image_url"):
        return entry
    recovery = image is None
    key = str(slide.get("media_key") or record["media_id"])
    if recovery:
        if not slide.get("image_url"):
            return entry
        # A signed CDN URL that has expired stays expired. Remember it so each
        # run does not request it again; a refreshed saved URL is tried anew.
        attempt = _url_attempt(slide["image_url"])
        if entry.get("flyer_expired_url") == attempt:
            return entry
        try:
            image = _download_image(slide["image_url"])
        except ImageExpired as exc:
            log.warning("post flyer URL expired for %s: %s", key, exc)
            stats.bump("flyer_recovery_failed")
            return {**entry, "flyer_expired_url": attempt}
        except Exception as exc:  # noqa: BLE001 - keep usable OCR if the download fails.
            log.warning("post flyer download failed for %s: %s", key, exc)
            stats.bump("flyer_recovery_failed")
            return entry
    durable = _upload_flyer(record, key, image)
    if not durable:
        if recovery:
            stats.bump("flyer_recovery_failed")
        return entry
    if recovery:
        stats.bump("flyers_recovered")
    return {**{k: v for k, v in entry.items() if k != "flyer_expired_url"}, "image_url": durable}


def process_post(record: dict[str, Any], stats: Stats | None = None, *,
                 cached_only: bool = False) -> dict[str, Any]:
    """Return this post's extraction, reading only what is not already cached."""
    stats = stats if stats is not None else Stats()
    media_id = str(record.get("media_id") or "")
    handle = str(record.get("handle") or "")
    label = f"post_{handle}_{media_id}" if handle and media_id else media_id or "unknown"
    if not media_id:
        log.warning("extract %s: missing media id", label)
        return {"status": "error", "error": "missing media id"}

    digest = fingerprint(record)

    cached: dict[str, Any] | None = None
    path = _cache_path(media_id)
    if path.exists():
        try:
            loaded = _read_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            log.warning("extract %s: unreadable cache: %s", label, exc)
        else:
            if isinstance(loaded, dict):
                cached = loaded
    remote = None
    if not _cached_decision_still_applies(record, cached):
        # A durable cache can recover OCR after the local data directory is lost.
        remote = _load_remote_cache(media_id)
        if _cached_decision_still_applies(record, remote):
            cached = _write_cache(media_id, remote)
    if _cached_decision_still_applies(record, cached):
        stats.bump("cache_hits")
        log.debug("extract %s: cache %s", label, cached.get("status"))
        slides = {slide.get("media_key"): slide for slide in _readable_slides(record)}
        images = [
            _ensure_durable_flyer(record, slides[entry.get("media_key")], entry, stats,
                                  cached_only=cached_only)
            if isinstance(entry, dict) and entry.get("media_key") in slides else entry
            for entry in cached.get("images") or []
        ]
        if images != (cached.get("images") or []):
            cached = _persist(media_id, {**cached, "images": images})
        return cached

    # A changed fingerprint invalidates the decision, never the image work:
    # slides whose media key is unchanged keep their OCR and QR results.
    reusable = {**known_images(remote), **known_images(cached)}
    slides = _readable_slides(record)
    selected_keys = {slide.get("media_key") for slide in slides}
    reusable = {key: entry for key, entry in reusable.items() if key in selected_keys}
    if cached_only and any(
        not slide.get("image_url")
        or reusable.get(slide.get("media_key"), {}).get("qr_scan_version") != QR_SCAN_VERSION
        for slide in slides
    ):
        stats.bump("pending")
        return {"status": "pending", "media_id": media_id, "handle": handle}

    images: list[dict[str, Any]] = []
    for slide in slides:
        key = str(slide.get("media_key") or "")
        if not slide.get("image_url"):
            # Missing media stays retryable rather than producing partial evidence.
            # Repairing a saved URL requires explicit maintenance.
            stats.bump("failed")
            log.warning("extract %s: slide %s has no image URL", label, key or slide.get("index"))
            return _persist_error(record, digest, "download",
                                  ValueError(f"slide {slide.get('index')} has no image URL"),
                                  images + list(reusable.values()))
        prior = reusable.get(key)
        if prior is not None and prior.get("qr_scan_version") == QR_SCAN_VERSION:
            entry = _ensure_durable_flyer(record, slide, prior, stats, cached_only=cached_only)
            images.append({**entry, "index": slide.get("index", len(images))})
            stats.bump("image_cache_hits")
            continue
        try:
            image = _download_image(slide.get("image_url"))
            stats.bump("download_successes")
        except ImageExpired as exc:
            # A saved URL needs explicit maintenance once it expires, so retrying
            # it every run only fails every publication. Set the post aside, like
            # a post this version cannot read: its earlier listing keeps support.
            stats.bump("expired_media")
            log.warning("extract %s: slide %s URL expired: %s", label, key, exc)
            return _persist_error(record, digest, "download", exc, images + list(reusable.values()),
                                  status="expired_media",
                                  detail={"media_key": key, "expired_url": _url_attempt(slide["image_url"])})
        except Exception as exc:  # noqa: BLE001 - per-post isolation.
            stats.bump("failed")
            log.warning("extract %s: slide %s download failed: %s", label, key, exc)
            return _persist_error(record, digest, "download", exc, images + list(reusable.values()))

        try:
            ocr_text = _vision_ocr(image)
        except Exception as exc:  # noqa: BLE001 - per-post isolation.
            stats.bump("failed")
            log.warning("extract %s: slide %s Vision OCR failed: %s", label, key, exc)
            return _persist_error(record, digest, "ocr", exc, images + list(reusable.values()))
        stats.bump("ocr_calls")

        try:
            qr_urls = qr_rsvp_urls(image)
        except Exception as exc:  # noqa: BLE001 - QR recovery must not lose a post.
            log.warning("extract %s: slide %s QR decoding failed: %s", label, key, exc)
            qr_urls = []
        entry = {
            "media_key": key,
            "index": slide.get("index", len(images)),
            "ocr_text": ocr_text,
            "qr_urls": qr_urls,
            "qr_scan_version": QR_SCAN_VERSION,
        }
        # Any slide can supply the cited evidence and become the event's flyer.
        entry = _ensure_durable_flyer(record, slide, entry, stats,
                                      cached_only=cached_only, image=image)
        images.append(entry)
        reusable[key] = entry

    if not images:
        stats.bump("skipped")
        log.info("extract %s: no_media", label)
        status = "no_media"
    elif not (record.get("caption") or "").strip() and not any(
        entry.get("ocr_text", "").strip() for entry in images
    ):
        # Nothing at all to read: no caption, no printed text. There is no
        # evidence any assessment could ever ground an event on.
        stats.bump("skipped")
        log.info("extract %s: no_text", label)
        status = "no_text"
    else:
        stats.bump("extracted")
        status = "ok"
    log.info("extract %s: %s (%d slides)", label, status, len(images))
    return _persist(media_id, {
        "status": status, "media_id": media_id, "handle": handle,
        "fingerprint": digest, "extraction_version": EXTRACTION_VERSION,
        "caption": record.get("caption"), "images": images,
        "extracted_at": _utc_now(),
    })


def _persist_error(
    record: dict[str, Any],
    digest: str,
    stage: str,
    exc: Exception,
    images: list[dict[str, Any]],
    *, status: str = "error",
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Keep a failure inspectable without discarding paid work.

    The slides that succeeded are stored inside the error payload and match by
    media key on the next run, so a partial media failure costs only the slides
    that actually failed. An expired_media payload keeps them the same way, for
    when its URL is refreshed.
    """
    keep: dict[str, dict[str, Any]] = {}
    for entry in images:
        key = entry.get("media_key")
        if isinstance(key, str) and key:
            keep.setdefault(key, entry)
    return _persist(str(record["media_id"]), {
        "status": status, "media_id": str(record["media_id"]),
        "handle": record.get("handle"), "fingerprint": digest,
        "extraction_version": EXTRACTION_VERSION, "caption": record.get("caption"),
        "images": list(keep.values()),
        "result": {"stage": stage, "error": f"{type(exc).__name__}: {exc}", **(detail or {})},
        "extracted_at": _utc_now(),
    })


def ordered_slides(cached: dict[str, Any]) -> list[dict[str, Any]]:
    """Cached slides in carousel order — the order evidence is numbered in."""
    entries = [entry for entry in (cached.get("images") or []) if isinstance(entry, dict)]
    return sorted(entries, key=lambda entry: entry.get("index", 0))


def _known_handles() -> set[str] | None:
    """The crawl roster, or None when it could not be read at all.

    None means "do not filter", which is different from an empty roster: a
    roster that failed to load says nothing about the archive, so extraction
    falls back to reading all of it rather than silently going dark.
    """
    try:
        return {account["handle"] for account in load_accounts() if account.get("handle")}
    except Exception as exc:  # noqa: BLE001 - fall back to the whole archive.
        log.warning("post extract: account roster unavailable: %s", exc)
        return None


def extract_all(handles: Iterable[str] | None = None, *,
                cached_only: bool = False,
                archive: ArchiveIndex) -> tuple[list[tuple[dict, dict]], Stats]:
    """Read every archived post once. Returns (record, extraction) pairs.

    `handles` None leaves the roster to decide; a caller-supplied set filters
    to exactly those accounts, and an empty one filters to none of them. An
    empty roster must not widen into the whole archive: that would OCR, assess,
    and publish every account ever crawled, including the ones dropped from
    accounts.json on purpose.
    """
    ensure_post_dirs()
    # Extraction publishes whatever is on disk even when collection failed, so
    # it restores the archive itself rather than trusting the collector to have.
    hydrate_local_posts(archive=archive)
    stats = Stats()
    roster = set(handles) if handles is not None else _known_handles()
    processed: list[tuple[dict[str, Any], dict[str, Any]]] = []
    streaks: dict[str, int] = {}
    for record in iter_local_posts(roster):
        before = {stage: stats.get(counter, 0) for stage, counter in
                  (("download", "download_successes"), ("ocr", "ocr_calls"))}
        try:
            cached = process_post(record, stats, cached_only=cached_only)
        except (Exception, SystemExit) as exc:
            cached = {"status": "error", "media_id": record["media_id"],
                      "result": {"error": f"{type(exc).__name__}: {exc}"}}
        processed.append((record, cached))
        live = False
        for stage, counter in (("download", "download_successes"), ("ocr", "ocr_calls")):
            if stats.get(counter, 0) > before[stage]:
                streaks[stage] = 0
                live = True
        if live and cached.get("status") != "error":
            # A post finished with live work: the unattributed path works too.
            streaks["unknown"] = 0
        if cached.get("status") == "expired_media":
            # Expiry belongs to this saved image, not the OCR/download service.
            # It neither advances nor clears a streak of actual service failures.
            continue
        if cached.get("status") != "error":
            continue
        failed = {"handle": record.get("handle"), "media_id": record["media_id"],
                  "detail": cached.get("result") or cached.get("error")}
        stats.bump("errors")
        stats.setdefault("first_error", failed)
        stage = (cached.get("result") or {}).get("stage", "unknown")
        streaks[stage] = streaks.get(stage, 0) + 1
        streak = streaks[stage]
        if streak >= MAX_CONSECUTIVE_FAILURES:
            stats["stopped_at"] = failed
            log.error("Extraction stopped after %d failures in a row: %s", streak, failed)
            break
        log.warning("Extraction failed; continuing: %s", failed)
    stats["posts"] = len(processed)
    log.info("extract posts: %s", dict(sorted(stats.items())))
    return processed, stats


def main(*, notify: bool = True, handles: Iterable[str] | None = None,
         publish: bool = True, report: Path | None = None) -> None:
    """Extract archived posts and, unless told otherwise, publish them.

    `publish=False` with a `report` is the pilot mode: it reads the posts, runs
    the assessment, and writes the source evidence and generated rows out for
    inspection without touching the events table or sending notifications.
    """
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    processed, stats = extract_all(handles, archive=ArchiveIndex())
    import assessed_events as publication
    from config import load_account_meta

    meta = load_account_meta()
    now = datetime.now(timezone.utc).isoformat()
    if publish:
        publication.publish_posts(processed, now, notify=notify, meta=meta)
        return

    assessment: dict[str, int] = {}
    updates = publication.post_updates(processed, meta, now, stats=assessment)
    rows = sum(len(item["rows"]) for item in updates)
    failed = sum(item["assessment"]["status"] == "error" for item in updates)
    log.info("Dry run: %d post source(s), %d event row(s), %d failed; extraction %s; assessment %s",
             len(updates), rows, failed, dict(sorted(stats.items())), dict(sorted(assessment.items())))
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(updates, ensure_ascii=False, indent=2))
        log.info("Wrote %s", report)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handle", action="append",
                        help="limit extraction to this account (repeatable); for pilots")
    parser.add_argument("--dry-run", action="store_true",
                        help="assess and map rows without publishing or notifying")
    parser.add_argument("--report", type=Path,
                        help="write the source evidence and generated rows here")
    parser.add_argument("--no-notify", action="store_true",
                        help="publish without sending Discord notifications")
    args = parser.parse_args()
    main(notify=not args.no_notify, handles=args.handle,
         publish=not args.dry_run, report=args.report)
