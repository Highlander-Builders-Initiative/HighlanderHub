"""Assess imported sources and reconcile their published event projections.

Both importers use this boundary. Raw OCR/extraction caches are retained as
source material; versioned assessments and publication ownership live in
source_assessments. Backfills never fetch media, run OCR, or send notifications.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import content_assessment as semantic
from classify import classify_content_kind
from config import DATA_DIR
from event_identity import dedupe_event_rows

log = logging.getLogger("pipeline.assessed_events")
CACHE_DIR = DATA_DIR / "assessments"


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

    Reviewed decisions still validate, and expire when source text or assessment
    policy changes. This is useful for curated regressions and sensitive sources.
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
        rows = client().table("source_assessments").select("*").order("source_key").range(offset, offset + 999).execute().data or []
        records.update((row["source_key"], row) for row in rows)
        if len(rows) < 1000:
            return records
    raise RuntimeError("Source assessment pagination exceeded its safety limit")


def cached_assessment(source: dict, prior: dict | None = None) -> dict:
    key = source["source_key"]
    path = _cache_path(key)
    digest = semantic.fingerprint(source)
    candidates = [prior or {}]
    if path.exists():
        try:
            candidates.insert(0, json.loads(path.read_text()))
        except (ValueError, OSError):
            pass
    for cached in candidates:
        if (isinstance(cached, dict) and cached.get("version") == semantic.VERSION
                and (cached.get("model") == semantic.MODEL or (cached.get("method") == "reviewed" and cached.get("reviewer")))
                and cached.get("source_hash") == digest
                and cached.get("status") == "complete"):
            try:
                semantic.validate(cached.get("result"), source)
                return cached
            except (ValueError, KeyError, TypeError):
                pass
    payload = {"version": semantic.VERSION, "model": semantic.MODEL, "source_hash": digest,
               "source": source, "assessed_at": datetime.now(timezone.utc).isoformat()}
    try:
        payload.update(status="complete", result=semantic.assess(source))
    except Exception as exc:
        # A failed call never becomes a negative classification. Publication
        # preserves the previous support set and retries next run.
        payload.update(status="error", error=f"{type(exc).__name__}: {exc}")
        log.warning("Assessment failed for %s: %s", key, payload["error"])
    return _save_assessment(payload)


def story_source(raw: dict, cached: dict) -> dict:
    post = raw.get("reshared_post") or {}
    texts = {"ocr_text": cached.get("ocr_text") or "", "caption": raw.get("caption") or "",
             "post_caption": post.get("caption") or ""}
    return {"source_key": f"instagram:{raw['id']}", "origin": "instagram",
            "posted_at": raw.get("posted_at"), "texts": texts, "source_occurrences": []}


def structured_source(raw: dict, origin: str) -> dict:
    import normalize_events as structured
    if origin == "localist":
        title = raw.get("title") or ""
        description = raw.get("description_text") or structured._strip_html(raw.get("description"))
        instances = structured._extract_instances(raw.get("event_instances"))
        occurrences = [{"id": str(i.get("id") or i["start"]), "starts_at": i["start"], "ends_at": i.get("end")}
                       for i in instances]
        if not occurrences:
            start, end = structured._start_end(raw)
            occurrences = [{"id": str(raw["id"]), "starts_at": start, "ends_at": end}] if start else []
    else:
        title, description = raw.get("name") or "", structured._strip_html(raw.get("description"))
        occurrences = [{"id": str(raw["id"]), "starts_at": raw["startsOn"], "ends_at": raw.get("endsOn")}] if raw.get("startsOn") else []
    for item in occurrences:
        if item.get("ends_at") == item["starts_at"]:
            item["ends_at"] = None
    occurrences.sort(key=lambda item: (item["starts_at"], item["id"]))
    return {"source_key": f"{origin}:{raw['id']}", "origin": origin,
            "texts": {"title": title, "description": description,
                      "dates": json.dumps(occurrences, sort_keys=True)},
            "source_occurrences": occurrences}


def assessment_occurrences(result: dict, source: dict) -> list[dict]:
    if result["schedule"]:
        return semantic.expand_schedule(result["schedule"], source, result)
    return result["occurrences"]


def story_rows(raw: dict, cached: dict, payload: dict, meta: dict, now: str) -> tuple[list[dict], set[str]]:
    import extract_stories as ig
    legacy, retired = ig._to_event_row(raw, cached, meta.get(raw.get("handle"), {}), now, meta)
    known = set(retired)
    if legacy:
        known.add(legacy["id"])
    # Even a cached not_event decision can have replaced an earlier positive.
    old = cached.get("result") or {}
    old_start = ig.normalize_timestamptz(old.get("starts_at"))
    for handle in (raw.get("handle"), ig._reshared_owner(raw), ig._reshared_media_identity(raw),
                   ig.reshared_origin_handle(cached.get("ocr_text"), raw.get("handle") or "", meta)):
        if handle and old_start:
            known.add(ig._instagram_event_id(handle, old_start))
    if payload["status"] != "complete":
        return [], known
    result = payload["result"]
    rows = []
    for occurrence in assessment_occurrences(result, payload["source"]):
        # The semantic validator has already established the occurrence's
        # activity/date evidence. Legacy OCR repair must not replace it with
        # an unrelated date or the bounds of its seasonal schedule.
        mapped_cache = {**cached, "status": "ok", "result": {
            **old, **{k: occurrence[k] for k in ("title", "starts_at", "ends_at", "location")},
            "is_event": True,
        }}
        row, aliases = ig._to_event_row(raw, mapped_cache, meta.get(raw.get("handle"), {}), now, meta,
                                        assessed_kind=result["kind"])
        known |= aliases
        if row and row["content_kind"] in {"student_event", "student_deadline"}:
            rows.append(row)
    # Distinct sessions at the same instant must not overwrite one another.
    return _disambiguate(rows), known


def _disambiguate(rows: list[dict]) -> list[dict]:
    titles: dict[str, set[str]] = {}
    for row in rows:
        titles.setdefault(row["id"], set()).add(row["title"])
    return [{**row, "id": row["id"] + "_" + hashlib.sha256(row["title"].encode()).hexdigest()[:10]}
            if len(titles[row["id"]]) > 1 else row for row in rows]


def structured_rows(raw: dict, origin: str, payload: dict, now: str) -> tuple[list[dict], set[str]]:
    import normalize_events as structured
    mapper = structured._to_event_row if origin == "localist" else structured._to_event_row_hlink
    fallback = mapper(raw, now)
    candidates = structured._to_event_rows(raw, now) if origin == "localist" else ([fallback] if fallback else [])
    known = {row["id"] for row in candidates}
    if fallback:
        known.add(fallback["id"])
    if payload["status"] != "complete":
        return [], known
    result = payload["result"]
    rows = candidates if result["use_source_occurrences"] else []
    if not result["use_source_occurrences"] and fallback:
        for occurrence in assessment_occurrences(result, payload["source"]):
            stamp = datetime.fromisoformat(occurrence["starts_at"]).astimezone(timezone.utc).strftime("%Y%m%dT%H%MZ")
            rows.append({**fallback, **{k: occurrence[k] for k in ("title", "starts_at", "ends_at")},
                         "location": occurrence["location"].strip() or fallback["location"],
                         "id": f"{fallback['id']}_{stamp}"})
    audiences = structured._filter_names(raw, "event_audience") if origin == "localist" else []
    public = []
    for row in rows:
        kind = classify_content_kind(origin, title=row["title"], description=row["description"],
                                     audiences=audiences, assessed_kind=result["kind"])
        if kind in {"student_event", "student_deadline"}:
            public.append({**row, "content_kind": kind})
    return _disambiguate(public), known


def make_update(source: dict, raw: dict, cached: dict | None, prior: dict | None, meta: dict, now: str) -> dict:
    payload = cached_assessment(source, (prior or {}).get("assessment"))
    try:
        rows, known = (story_rows(raw, cached, payload, meta, now) if source["origin"] == "instagram"
                       else structured_rows(raw, source["origin"], payload, now))
    except Exception as exc:
        payload = {**payload, "status": "error", "error": f"Mapping failed: {type(exc).__name__}: {exc}"}
        rows, known = [], set()
    return {"source_key": source["source_key"], "origin": source["origin"], "assessment": payload,
            "rows": dedupe_event_rows(rows), "known_event_ids": sorted(known)}


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
        raise RuntimeError(f"{len(failed)} source assessment(s) failed; previous listings retained: {', '.join(failed)}")


def publish_stories(processed: list[tuple[dict, dict]], meta: dict, now: str, *, notify: bool) -> None:
    import extract_stories as ig
    registry = load_registry()
    updates = []
    # Share the original author across reshares of the same attached post,
    # preserving the importer’s canonical identity even when one copy omits it.
    owners: dict[str, set[str]] = {}
    for raw, cached in processed:
        media = ig._reshared_media_identity(raw)
        owner = ig._reshared_owner(raw) or ig.reshared_origin_handle(cached.get("ocr_text"), raw.get("handle") or "", meta)
        if media and owner:
            owners.setdefault(media, set()).add(owner)
    for raw, cached in processed:
        candidates = owners.get(ig._reshared_media_identity(raw), set())
        if len(candidates) == 1 and not ig._reshared_owner(raw):
            raw = {**raw, "reshared_post": {**raw["reshared_post"], "owner_username": next(iter(candidates))}}
        source = story_source(raw, cached)
        if cached.get("status") == "error":
            updates.append({"source_key": source["source_key"], "origin": "instagram",
                            "assessment": {"status": "error", "error": "Source extraction failed"}, "rows": [], "known_event_ids": []})
        elif any(source["texts"].values()):
            updates.append(make_update(source, raw, cached, registry.get(source["source_key"]), meta, now))
    _complete(updates, notify=notify)


def publish_structured(raws: list[tuple[str, dict]], verified_prefixes: set[str], now: str, *, notify: bool) -> None:
    registry = load_registry()
    updates = []
    for origin, raw in raws:
        source = structured_source(raw, origin)
        updates.append(make_update(source, raw, None, registry.get(source["source_key"]), {}, now))
    present = {item["source_key"] for item in updates}
    verified_origins = {origin for prefix, origin in (("ucr_events_", "localist"), ("highlander_link_", "highlander_link")) if prefix in verified_prefixes}
    # Bootstrap vanished legacy sources as well. Before the first assessed run
    # their IDs exist only in events, and a complete source snapshot must still
    # remove them as the previous normalizer did.
    missing_legacy: dict[str, list[str]] = {}
    if verified_origins:
        from db import get_imported_events
        for row in get_imported_events():
            for prefix, origin in (("ucr_events_", "localist"), ("highlander_link_", "highlander_link")):
                if origin in verified_origins and row["id"].startswith(prefix):
                    key = f"{origin}:{row['id'][len(prefix):].split('_', 1)[0]}"
                    if key not in present:
                        missing_legacy.setdefault(key, []).append(row["id"])
    for key, record in registry.items():
        if record["origin"] in verified_origins and key not in present:
            missing_legacy.setdefault(key, [])
    for key, ids in missing_legacy.items():
        updates.append({"source_key": key, "origin": key.split(':', 1)[0], "rows": [], "known_event_ids": ids,
                        "assessment": {"status": "complete", "reason": "Absent from a verified complete source snapshot"}})
    _complete(updates, notify=notify)


def main() -> None:
    """Backfill saved source text; default dry-run, no scrape/OCR/notifications."""
    import extract_stories as ig
    import normalize_events as structured
    from db import get_imported_events

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--source", action="append", help="source key, e.g. instagram:3977797394086504274")
    parser.add_argument("--active", action="store_true", help="reassess sources supporting currently visible imported listings")
    parser.add_argument("--report", type=Path, default=DATA_DIR / "assessment-report.json")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    registry = load_registry()
    now = datetime.now(timezone.utc)
    meta = ig._load_account_meta()
    existing = get_imported_events()
    active = [row for row in existing if (structured._parse_iso(row.get("ends_at") or row.get("starts_at")) or now) >= now]
    active_ids = {row["id"] for row in active}
    selected = set(args.source or [])
    sources = []
    # The saved archive is independent of today's followed-account list.
    for path in sorted(ig.RAW_DIR.glob("*/*.json")):
        if path.parent.name in {"ucr_events", "highlander_link"}:
            continue
        raw = ig._read_json(path)
        cache = ig._cache_path(str(raw.get("id")))
        if cache.exists():
            cached = ig._read_json(cache)
            if cached.get("status") in {"ok", "not_event"}:
                sources.append((story_source(raw, cached), raw, cached))
    for origin, directory in (("localist", structured.UCR_EVENTS_RAW), ("highlander_link", structured.HIGHLANDER_LINK_RAW)):
        for raw in structured._collect_raw(directory):
            sources.append((structured_source(raw, origin), raw, None))
    updates = []
    for source, raw, cached in sources:
        key = source["source_key"]
        if selected and key not in selected:
            continue
        if not any(source["texts"].values()):
            continue
        if args.active:
            prior_ids = set(registry.get(key, {}).get("event_ids", []))
            empty = {"status": "error"}
            _, legacy_ids = (story_rows(raw, cached, empty, meta, now.isoformat()) if cached is not None
                             else structured_rows(raw, source["origin"], empty, now.isoformat()))
            story_id = str(raw.get("id"))
            url_match = source["origin"] == "instagram" and any(f"/{story_id}/" in (row.get("source_url") or "") for row in active)
            if not (active_ids & (prior_ids | legacy_ids)) and not url_match:
                continue
        log.info("Assessing %s", key)
        update = make_update(source, raw, cached, registry.get(key), meta, now.isoformat())
        # Bootstrap ownership using actual stored source URLs, including rows
        # generated by legacy versions whose identity cannot be reconstructed.
        if source["origin"] == "instagram":
            update["known_event_ids"] = sorted(set(update["known_event_ids"]) | {
                row["id"] for row in existing if f"/{raw['id']}/" in (row.get("source_url") or "")})
        updates.append(update)
    missing = selected - {item["source_key"] for item in updates}
    if missing:
        raise RuntimeError(f"Requested sources have no usable saved evidence: {sorted(missing)}")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(updates, ensure_ascii=False, indent=2))
    log.info("%s: %d sources; %d assessed rows; %d errors; report %s",
             "Applying" if args.apply else "Dry run", len(updates), sum(len(item["rows"]) for item in updates),
             sum(item["assessment"]["status"] == "error" for item in updates), args.report)
    if args.apply:
        _complete(updates, notify=False)


if __name__ == "__main__":
    main()
