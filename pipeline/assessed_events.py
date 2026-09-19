"""Assess imported sources and reconcile their published event projections.

Instagram posts use this boundary. Raw OCR/extraction caches are retained as
source material; versioned assessments and publication ownership live in
source_assessments. Backfills never fetch media, run OCR, or send notifications.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import content_assessment as semantic
from config import DATA_DIR, load_account_meta
from event_identity import dedupe_event_rows
from instagram_rows import build_instagram_row, instagram_event_id

log = logging.getLogger("pipeline.assessed_events")
CACHE_DIR = DATA_DIR / "assessments"
# A failed call is retried next run and assessment moves on; this many in a row
# means the model is down or the quota is spent, so stop spending calls.
MAX_CONSECUTIVE_FAILURES = 3


def _cache_path(source_key: str) -> Path:
    return CACHE_DIR / f"{hashlib.sha256(source_key.encode()).hexdigest()}.json"


def _save_assessment(payload: dict) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(payload["source"]["source_key"])
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    temporary.replace(path)
    return payload


def record_review(source: dict, result: dict, *, reviewer: str) -> dict:
    """Record an explicit source review without pretending a model ran.

    Reviewed decisions still validate, and expire when source text changes or a
    refresh is explicitly requested. This is useful for curated regressions.
    """
    if not reviewer.strip():
        raise ValueError("Review requires attribution")
    return _save_assessment({"version": semantic.VERSION, "method": "reviewed", "reviewer": reviewer,
                            "source_hash": semantic.fingerprint(source), "source": source,
                            "assessed_at": datetime.now(timezone.utc).isoformat(), "status": "complete",
                            "result": semantic.validate(result, source)})


def load_registry() -> dict[str, dict]:
    from db import client
    records = {}
    for offset in range(0, 1_000_000, 1000):
        rows = client().table("source_assessments").select("*").eq("origin", "instagram").order("source_key").range(offset, offset + 999).execute().data or []
        records.update((row["source_key"], row) for row in rows)
        if len(rows) < 1000:
            return records
    raise RuntimeError("Source assessment pagination exceeded its safety limit")


def _assessment_candidates(source: dict, prior: dict | None) -> list[dict]:
    path = _cache_path(source["source_key"])
    candidates = [prior or {}]
    if path.exists():
        try:
            candidates.insert(0, json.loads(path.read_text()))
        except (ValueError, OSError):
            pass
    # A stale local file must not replace a newer correction in the registry.
    return sorted((item for item in candidates if isinstance(item, dict)),
                  key=lambda item: item.get("assessed_at") or "", reverse=True)


def cached_assessment(source: dict, prior: dict | None = None, stats: dict | None = None,
                      *, refresh: bool = False, persist: bool = True) -> dict:
    """Reuse source-matched decisions until an explicit refresh or text change.

    Version and model are provenance only while automatic policy invalidation
    is paused. Do not revalidate old decisions under new rules here: a small
    validator change must not silently trigger a paid archive-wide rerun.
    Newly generated/reviewed decisions still pass semantic validation.
    """
    key = source["source_key"]
    digest = semantic.fingerprint(source)
    for cached in [] if refresh else _assessment_candidates(source, prior):
        if cached.get("source_hash") != digest:
            continue
        if cached.get("status") == "complete" and isinstance(cached.get("result"), dict):
            if stats is not None:
                stats["assessment_cache_hits"] = stats.get("assessment_cache_hits", 0) + 1
            return cached
        # A refused answer is a decision about this exact text, not an outage.
        # Keep it until the text changes or a refresh is explicitly requested.
        if cached.get("status") == "error" and cached.get("retryable") is False:
            if stats is not None:
                stats["rejections_skipped"] = stats.get("rejections_skipped", 0) + 1
            return cached
    payload = {"version": semantic.VERSION, "model": semantic.MODEL, "source_hash": digest,
               "source": source, "assessed_at": datetime.now(timezone.utc).isoformat()}
    if stats is not None:
        stats["model_calls"] = stats.get("model_calls", 0) + 1
    try:
        payload.update(status="complete", result=semantic.assess(source))
    except semantic.GroundingRejected as exc:
        # The source was assessed and refused. Recorded as a decision so the
        # next run is not spent earning the same refusal.
        payload.update(status="error", error=f"{type(exc).__name__}: {exc}", retryable=False)
        payload["validation_attempts"] = exc.attempts
        log.warning("Assessment refused for %s: %s", key, payload["error"])
    except Exception as exc:
        # A failed call never becomes a negative classification. Publication
        # preserves the previous support set and retries next run.
        payload.update(status="error", error=f"{type(exc).__name__}: {exc}", retryable=True)
        log.warning("Assessment failed for %s: %s", key, payload["error"])
    return _save_assessment(payload) if persist else payload


def _event_relevance(row: dict, now: str) -> bool | None:
    """Today/future in campus time; None means no usable event date is known."""
    value = row.get("ends_at") or row.get("starts_at")
    if not isinstance(value, str) or not value:
        return None
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=semantic.PACIFIC)
        today = datetime.fromisoformat(now.replace("Z", "+00:00")).astimezone(semantic.PACIFIC).replace(
            hour=0, minute=0, second=0, microsecond=0)
        # Ends are exclusive: an event ending at today's midnight finished
        # yesterday. An event starting at that midnight belongs to today.
        return instant > today if row.get("ends_at") else instant >= today
    except ValueError:
        return None


def _source_is_past(source: dict, prior: dict | None, now: str) -> bool:
    """Skip known finished sources before any semantic call, including retries.

    Instagram uses its last assessment. A post's upload timestamp is never
    used as its event date. Undated/new content needs its first assessment.
    """
    dates = []
    previous = (prior or {}).get("last_complete_assessment") or (prior or {}).get("assessment")
    for candidate in _assessment_candidates(source, previous):
        result = candidate.get("result") or {}
        dates = result.get("occurrences") or []
        if result.get("schedule"):
            dates = [{"starts_at": result["schedule"].get("last_day")}]
        if dates:
            break
    return bool(dates) and all(_event_relevance(row, now) is False for row in dates)


# Carousel slides are numbered from 1 in the source text so a citation names a
# specific image. Keeping each slide in its own field is what makes activity,
# date, and location evidence attributable to the slide that actually printed it.
_SLIDE_FIELD = re.compile(r"^slide_(\d+)_ocr$")


def post_source(record: dict, cached: dict) -> dict:
    """A feed post as assessable source text: caption plus per-slide OCR.

    A post with no printed text at all is still assessable — the caption can
    carry the whole announcement — so an empty slide set is not a refusal here.
    """
    import extract_posts as posts
    texts = {"caption": record.get("caption") or ""}
    for slide in posts.ordered_slides(cached):
        texts[f"slide_{int(slide.get('index', 0)) + 1}_ocr"] = slide.get("ocr_text") or ""
    # Keep the empty occurrence field to preserve existing source fingerprints.
    return {"source_key": f"instagram:post:{record['media_id']}", "origin": "instagram",
            "posted_at": record.get("posted_at"), "texts": texts, "source_occurrences": []}


def assessment_occurrences(result: dict, source: dict) -> list[dict]:
    if result["schedule"]:
        return semantic.expand_schedule(result["schedule"], source, result)
    return result["occurrences"]


def _evidence_slides(result: dict, occurrence: dict) -> list[int]:
    """Zero-based indices of the slides cited as evidence, in slide order."""
    found: set[int] = set()
    for evidence in (result.get("activity_evidence"), result.get("date_evidence"), result.get("location_evidence"),
                     occurrence.get("activity_evidence"), occurrence.get("date_evidence"), occurrence.get("location_evidence")):
        for item in evidence or []:
            match = _SLIDE_FIELD.match(str((item or {}).get("field") or "")) if isinstance(item, dict) else None
            if match:
                found.add(int(match.group(1)) - 1)
    return sorted(found)


def post_rows(record: dict, cached: dict, payload: dict, meta: dict, now: str) -> tuple[list[dict], set[str]]:
    """Map one assessed post to at most one published event row.

    Posts carry a single announcement by design: a club posting a whole term's
    schedule as one carousel cannot be turned into one listing without choosing
    a session for the reader. Those are skipped with a reason rather than
    guessed at.
    """
    import extract_posts as posts
    from event_dates import normalize_timestamptz

    known: set[str] = set()
    if payload["status"] != "complete":
        return [], known
    result = payload["result"]
    occurrences = assessment_occurrences(result, payload["source"])
    if not occurrences:
        return [], known
    if len(occurrences) > 1:
        log.info("post %s: skipping %d occurrences; a post publishes exactly one event",
                 record.get("media_id"), len(occurrences))
        return [], known

    occurrence = occurrences[0]
    owner = str(record.get("owner_username") or record.get("handle") or "").strip().lower()
    starts_at = normalize_timestamptz(occurrence.get("starts_at"))
    title = str(occurrence.get("title") or "").strip()
    if not starts_at or not title:
        return [], known

    slides = posts.ordered_slides(cached)
    by_index = {int(slide.get("index", position)): slide
                for position, slide in enumerate(slides)}
    ocr_text = "\n".join(str(slide.get("ocr_text") or "") for slide in slides)
    caption = str(record.get("caption") or "")

    event_id = instagram_event_id(owner, record.get("media_id"))
    if event_id:
        known.add(event_id)
    # The flyer is the first slide whose text was actually cited. A caption-only
    # event has no cited slide, so the post's lead image represents it.
    cited = [index for index in _evidence_slides(result, occurrence) if index in by_index]
    flyer = by_index.get(cited[0]) if cited else (slides[0] if slides else {})

    row = build_instagram_row(
        record, {**occurrence, "description": caption}, identity_handle=owner, host_handle=owner,
        account_meta=meta.get(owner) or meta.get(record.get("handle")) or {},
        text=f"{caption}\n{ocr_text}", image_url=(flyer or {}).get("image_url"),
        qr_urls=[url for slide in slides for url in slide.get("qr_urls") or []],
        scraped_at=now, assessed_kind=result["kind"],
    )
    return ([row] if row and row["content_kind"] in {"student_event", "student_deadline"} else []), known


def make_update(source: dict, raw: dict, cached: dict | None, prior: dict | None, meta: dict,
                now: str, stats: dict | None = None, *, refresh: bool = False,
                persist: bool = True) -> dict | None:
    if _source_is_past(source, prior, now):
        if stats is not None:
            stats["past_sources_skipped"] = stats.get("past_sources_skipped", 0) + 1
        log.debug("Skipping finished source %s", source["source_key"])
        return None
    payload = cached_assessment(source, (prior or {}).get("assessment"), stats,
                                refresh=refresh, persist=persist)
    try:
        rows, known = post_rows(raw, cached, payload, meta, now)
    except Exception as exc:
        payload = {**payload, "status": "error", "error": f"Mapping failed: {type(exc).__name__}: {exc}"}
        rows, known = [], set()
    # Proposed IDs are not historical aliases. Calling a replacement "known"
    # would bypass the RPC's protection for locked/deleted legacy identities.
    # The RPC records accepted row IDs itself and merges stored source aliases.
    return {"source_key": source["source_key"], "origin": source["origin"], "assessment": payload,
            "rows": dedupe_event_rows(rows),
            "known_event_ids": sorted(known - {row["id"] for row in rows})}


def publish(updates: list[dict]) -> dict:
    """One transaction updates support, saves rows and retires unsupported IDs.

    Error updates retain existing ownership. The RPC rechecks locks and admin
    tombstones within the transaction and serializes competing import batches.
    """
    from db import client
    if not updates:
        return {"written": 0, "deleted": 0}
    return client().rpc("reconcile_source_assessments", {"updates": updates}).execute().data


def _complete(updates: list[dict], *, notify: bool) -> None:
    result = publish(updates)
    log.info("Assessed publication: %s", result)
    if notify:
        from db import get_event_rows_by_ids
        from discord_notify import notify_free_food_events
        candidate_ids = [
            row["id"]
            for item in updates
            if item["assessment"]["status"] == "complete"
            for row in item["rows"]
        ]
        try:
            published_rows = get_event_rows_by_ids(candidate_ids)
        except Exception as exc:  # noqa: BLE001 - notifications must not fail ingest.
            log.warning("Could not resolve published rows for Discord notification: %s", exc)
        else:
            notify_free_food_events(published_rows)
    failed = [item["source_key"] for item in updates if item["assessment"]["status"] == "error"]
    if failed:
        first = next(item for item in updates if item["assessment"]["status"] == "error")
        raise RuntimeError(f"{len(failed)} source assessment(s) failed; previous listings retained: {', '.join(failed)}; "
                           f"first failure: {first['assessment'].get('error')}")


def post_updates(processed: list[tuple[dict, dict]], meta: dict, now: str,
                 registry: dict | None = None, stats: dict | None = None,
                 *, stop_on_error: bool = False) -> list[dict]:
    """Build publication updates for collected posts.

    A usable extraction (`ok`) and a retryable failure (`error`) produce an
    update, and so does a post whose text has been taken away: `no_text` on a
    source that still supports a listing publishes the absence, because an
    emptied caption is a content change and the listing it produced has no
    evidence left. Removing the announcement must withdraw the same listing
    whether the caption was replaced with other words or deleted outright.

    A post this version could not read emits nothing, and an earlier listing
    keeps its support: `unsupported_media` is a limit of this reader (an
    over-long carousel) and `no_media` a defect in the archived record — a post
    always has at least one slide — so neither says anything about the event.
    """
    registry = load_registry() if registry is None else registry
    updates = []
    streak = 0
    for record, cached in processed:
        status = cached.get("status")
        if status not in {"ok", "error", "no_text"}:
            continue
        source = post_source(record, cached)
        prior = registry.get(source["source_key"])
        if status == "no_text":
            # Nothing is left to assess, so the withdrawal is published directly
            # rather than asked of the model. Sources that never published stay
            # silent: there is no listing for an absence to withdraw.
            supported = sorted((prior or {}).get("event_ids") or [])
            if not supported:
                continue
            log.info("post %s: caption and slide text removed; withdrawing %s",
                     record.get("media_id"), ", ".join(supported))
            updates.append({"source_key": source["source_key"], "origin": "instagram",
                            "assessment": {"status": "complete",
                                           "reason": "Source text was removed: the post has no caption and no printed text"},
                            "rows": [], "known_event_ids": supported})
        elif status == "error":
            updates.append({"source_key": source["source_key"], "origin": "instagram",
                            "assessment": {"status": "error", "error": "Post extraction failed"},
                            "rows": [], "known_event_ids": []})
        elif any(source["texts"].values()):
            try:
                update = make_update(source, record, cached, prior, meta, now, stats=stats)
            except (Exception, SystemExit) as exc:
                if not stop_on_error:
                    raise
                update = {"source_key": source["source_key"], "origin": "instagram",
                          "assessment": {"status": "error", "retryable": True,
                                         "error": f"{type(exc).__name__}: {exc}"},
                          "rows": [], "known_event_ids": []}
            if update is not None:
                updates.append(update)
                failure = update.get("assessment") or {}
                if not (stop_on_error and failure.get("status") == "error"
                        and failure.get("retryable") is not False):
                    streak = 0
                    continue
                streak += 1
                if streak >= MAX_CONSECUTIVE_FAILURES:
                    log.error("Assessment stopped after %d failures in a row at %s: %s",
                              streak, source["source_key"], failure.get("error"))
                    break
                log.warning("Assessment failed for %s; continuing: %s", source["source_key"], failure.get("error"))
    return updates


def publish_posts(processed: list[tuple[dict, dict]], now: str, *, notify: bool,
                  meta: dict | None = None) -> None:
    stats: dict[str, int] = {}
    updates = post_updates(processed, meta if meta is not None else load_account_meta(), now,
                           stats=stats, stop_on_error=True)
    log.info("Instagram publication: %d post source(s); %s",
             len(processed), dict(sorted(stats.items())) or "fully cached")
    _complete(updates, notify=notify)


def main() -> None:
    """Backfill today's/future listings; default dry-run, no scrape/OCR/notifications."""
    from db import get_imported_events

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--source", action="append", help="source key, e.g. instagram:post:3977797394086504274")
    parser.add_argument("--active", action="store_true", help="compatibility flag; backfills always select today's/future listings")
    parser.add_argument("--refresh", action="store_true", help="explicitly replace cached decisions for the selected today's/future listings")
    parser.add_argument("--retry-failed", action="store_true",
                        help="retry only failed assessments named by --source, including sources without a listing")
    parser.add_argument("--report", type=Path, default=DATA_DIR / "assessment-report.json")
    args = parser.parse_args()
    if args.retry_failed and not args.source:
        parser.error("--retry-failed requires at least one --source; archive-wide retries are not allowed")
    logging.basicConfig(level=logging.INFO)
    registry = load_registry()
    now = datetime.now(timezone.utc)
    meta = load_account_meta()
    existing = get_imported_events()
    active = [row for row in existing if _event_relevance(row, now.isoformat()) is True]
    active_ids = {row["id"] for row in active}
    selected = set(args.source or [])
    sources = []
    import extract_posts as igposts
    import post_archive
    # Reassessment names a source by key, so the post it names has to be on disk
    # — restore anything this machine is missing before deciding it is unknown.
    post_archive.hydrate_local_posts()
    for record in post_archive.iter_local_posts():
        path = igposts._cache_path(str(record.get("media_id")))
        if path.exists():
            cached = igposts._read_json(path)
            if cached.get("status") == "ok":
                sources.append((post_source(record, cached), record, cached))
    updates = []
    usable = set()
    skipped = 0
    for source, raw, cached in sources:
        key = source["source_key"]
        if selected and key not in selected:
            continue
        if not any(source["texts"].values()):
            continue
        usable.add(key)
        if args.retry_failed:
            candidates = _assessment_candidates(source, registry.get(key, {}).get("assessment"))
            latest = next((item for item in candidates
                           if item.get("source_hash") == semantic.fingerprint(source)), {})
            if latest.get("status") != "error":
                skipped += 1
                continue
        prior_ids = set(registry.get(key, {}).get("event_ids", []))
        marker = f"/p/{raw.get('shortcode')}/"
        url_match = any(marker in (row.get("source_url") or "") for row in active)
        if not args.retry_failed and not (active_ids & prior_ids) and not url_match:
            skipped += 1
            continue
        log.info("Assessing %s", key)
        update = make_update(source, raw, cached, registry.get(key), meta, now.isoformat(),
                             refresh=args.refresh or args.retry_failed,
                             persist=args.apply or not args.retry_failed)
        if update is None:
            skipped += 1
            continue
        # Bootstrap ownership using actual stored source URLs, including rows
        # generated by legacy versions whose identity cannot be reconstructed.
        update["known_event_ids"] = sorted(set(update["known_event_ids"]) | {
            row["id"] for row in existing if marker in (row.get("source_url") or "")})
        updates.append(update)
    missing = selected - usable
    if missing:
        raise RuntimeError(f"Requested sources have no usable saved evidence: {sorted(missing)}")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(updates, ensure_ascii=False, indent=2))
    log.info("%s: %d sources; %d assessed rows; %d errors; report %s",
             "Applying" if args.apply else "Dry run", len(updates), sum(len(item["rows"]) for item in updates),
             sum(item["assessment"]["status"] == "error" for item in updates), args.report)
    log.info("Skipped %d sources outside the selected reassessment scope or already finished", skipped)
    if args.apply:
        _complete(updates, notify=False)


if __name__ == "__main__":
    main()
