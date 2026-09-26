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
from typing import TYPE_CHECKING, NamedTuple

import content_assessment as semantic
from config import DATA_DIR, load_account_meta
from event_identity import dedupe_event_rows
from instagram_rows import POST_EVENT_ID, build_instagram_row, instagram_event_id

if TYPE_CHECKING:
    from reconcile_events import Reviews

log = logging.getLogger("pipeline.assessed_events")
CACHE_DIR = DATA_DIR / "assessments"
# A failed call is retried next run and assessment moves on; this many in a row
# means the model is down or the quota is spent, so stop spending calls.
MAX_CONSECUTIVE_FAILURES = 3
# More sessions than this in one post is a season schedule, not a week's plans.
MAX_SESSIONS = 10


class AssessmentResult(NamedTuple):
    """Assessment payload plus invocation provenance that is never persisted."""

    payload: dict
    produced_live: bool


class UpdateResult(NamedTuple):
    update: dict | None
    produced_live: bool


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
                      *, refresh: bool = False, persist: bool = True) -> AssessmentResult:
    """Reuse source-matched decisions until an explicit refresh or text change.

    Version and model are provenance only while automatic policy invalidation
    is paused. Do not revalidate old decisions under new rules here: a small
    validator change must not silently trigger a paid archive-wide rerun.
    Newly generated/reviewed decisions still pass semantic validation.
    The returned flag describes this invocation, separate from the saved payload.
    """
    key = source["source_key"]
    digest = semantic.fingerprint(source)
    for cached in [] if refresh else _assessment_candidates(source, prior):
        if cached.get("source_hash") != digest:
            continue
        if cached.get("status") == "complete" and isinstance(cached.get("result"), dict):
            if stats is not None:
                stats["assessment_cache_hits"] = stats.get("assessment_cache_hits", 0) + 1
            return AssessmentResult(cached, produced_live=False)
        # A refused answer is a decision about this exact text, not an outage.
        # Keep it until the text changes or a refresh is explicitly requested.
        if cached.get("status") == "error" and cached.get("retryable") is False:
            if stats is not None:
                stats["rejections_skipped"] = stats.get("rejections_skipped", 0) + 1
            return AssessmentResult(cached, produced_live=False)
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
    return AssessmentResult(_save_assessment(payload) if persist else payload, produced_live=True)


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


def _session_keys(occurrences: list[dict]) -> list[str | None]:
    """ID suffixes for the sessions of a post that lists several.

    A session is keyed by its UTC start minute, like legacy Instagram IDs. Two
    sessions starting together (an org fair and an open house at 4 PM) also
    carry their title. A post announcing one event keeps the post's own ID.
    """
    from event_dates import normalize_timestamptz

    if len(occurrences) < 2:
        return [None] * len(occurrences)
    stamps = []
    for occurrence in occurrences:
        starts_at = normalize_timestamptz(occurrence.get("starts_at"))
        stamps.append(datetime.fromisoformat(starts_at).astimezone(timezone.utc).strftime("%Y%m%dT%H%MZ")
                      if starts_at else None)
    keys = []
    for stamp, occurrence in zip(stamps, occurrences):
        if stamp is None or stamps.count(stamp) == 1:
            keys.append(stamp)
            continue
        title = re.sub(r"\s+", " ", str(occurrence.get("title") or "").casefold()).strip()
        keys.append(f"{stamp}-{hashlib.sha256(title.encode()).hexdigest()[:6]}")
    return keys


def post_rows(record: dict, cached: dict, payload: dict, meta: dict, now: str) -> tuple[list[dict], set[str]]:
    """Map one assessed post to its published event rows, one per session.

    A welcome-week carousel lists several sessions in one post; each becomes its
    own listing under the post's ID plus a session key, so the site's day and
    week views show every one of them. A post listing more than MAX_SESSIONS is
    a season schedule (every game, every info session) and publishes nothing.
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
    if len(occurrences) > MAX_SESSIONS:
        log.info("post %s: skipping %d sessions; a post listing more than %d is a season schedule",
                 record.get("media_id"), len(occurrences), MAX_SESSIONS)
        return [], known

    owner =str(record.get("owner_username") or record.get("handle") or "").strip().lower()
    slides = posts.ordered_slides(cached)
    by_index = {int(slide.get("index", position)): slide
                for position, slide in enumerate(slides)}
    ocr_text = "\n".join(str(slide.get("ocr_text") or "") for slide in slides)
    caption = str(record.get("caption") or "")

    rows = []
    for occurrence, session in zip(occurrences, _session_keys(occurrences)):
        starts_at = normalize_timestamptz(occurrence.get("starts_at"))
        title = str(occurrence.get("title") or "").strip()
        if not starts_at or not title:
            continue
        event_id = instagram_event_id(owner, record.get("media_id"), session)
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
            scraped_at=now, assessed_kind=result["kind"], session=session,
        )
        if row and row["content_kind"] in {"student_event", "student_deadline"}:
            rows.append(row)
    return rows, known


def make_update(source: dict, raw: dict, cached: dict | None, prior: dict | None, meta: dict,
                now: str, stats: dict | None = None, *, refresh: bool = False,
                persist: bool = True) -> UpdateResult:
    if _source_is_past(source, prior, now):
        if stats is not None:
            stats["past_sources_skipped"] = stats.get("past_sources_skipped", 0) + 1
        log.debug("Skipping finished source %s", source["source_key"])
        return UpdateResult(None, produced_live=False)
    payload, produced_live = cached_assessment(
        source, (prior or {}).get("assessment"), stats, refresh=refresh, persist=persist)
    try:
        rows, known = post_rows(raw, cached, payload, meta, now)
    except Exception as exc:
        payload = {**payload, "status": "error", "error": f"Mapping failed: {type(exc).__name__}: {exc}"}
        rows, known = [], set()
    # Local cache hits still need their first durable publication. Only an
    # identical registry decision proves that this update was already saved.
    # Keep complete updates with historical IDs: reconciliation may still need
    # to retire an old listing (including one whose lock was just removed).
    result = payload.get("result") or {}
    negative = (payload["status"] == "complete"
                and not result.get("occurrences") and not result.get("schedule")
                and (prior or {}).get("event_ids") == []
                and (prior or {}).get("known_event_ids") == [])
    refused = payload["status"] == "error" and payload.get("retryable") is False
    if (not rows and not known and payload == (prior or {}).get("assessment")
            and (negative or refused)):
        if stats is not None:
            stats["unchanged_decisions_skipped"] = stats.get("unchanged_decisions_skipped", 0) + 1
        return UpdateResult(None, produced_live=produced_live)
    # Proposed IDs are not historical aliases. Calling a replacement "known"
    # would bypass the RPC's protection for locked/deleted legacy identities.
    # The RPC records accepted row IDs itself and merges stored source aliases.
    return UpdateResult({
        "source_key": source["source_key"], "origin": source["origin"], "assessment": payload,
        "rows": dedupe_event_rows(rows),
        "known_event_ids": sorted(known - {row["id"] for row in rows}),
    }, produced_live=produced_live)


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
    # A refusal is a decision about this exact source text, not an outage. It is
    # already recorded, costs nothing to keep, and cannot change until the text
    # does or a refresh is asked for. Reporting it as a run failure would leave
    # every future run red — a refused source carries no occurrence dates, so
    # `_source_is_past` can never age it out — and bury the failures that a
    # rerun could still clear.
    refused = sorted({item["source_key"] for item in updates
                      if item["assessment"]["status"] == "error"
                      and item["assessment"].get("retryable") is False})
    if refused:
        log.info("%d source(s) stay refused and publish nothing: %s", len(refused), ", ".join(refused))
    unresolved = [item for item in updates if item["assessment"]["status"] == "error"
                  and item["assessment"].get("retryable") is not False]
    if unresolved:
        failed = [item["source_key"] for item in unresolved]
        raise RuntimeError(f"{len(failed)} source assessment(s) failed; existing listings, if any, retained: {', '.join(failed)}; "
                           f"first failure: {unresolved[0]['assessment'].get('error')}")


def post_updates(processed: list[tuple[dict, dict]], meta: dict, now: str,
                 registry: dict | None = None, stats: dict | None = None,
                 *, stop_on_error: bool = False,
                 canonical: dict[str, dict] | None = None, reviews: Reviews | None = None) -> list[dict]:
    """Build publication updates for collected posts.

    A usable extraction (`ok`) and a retryable failure (`error`) produce an
    update, and so does a post whose text has been taken away: `no_text` on a
    source that still supports a listing publishes the absence, because an
    emptied caption is a content change and the listing it produced has no
    evidence left. Removing the announcement must withdraw the same listing
    whether the caption was replaced with other words or deleted outright.

    A post this version could not read emits nothing, and an earlier listing
    keeps its support: `unsupported_media` is a limit of this reader (an
    over-long carousel), `no_media` a defect in the archived record — a post
    always has at least one slide — and `expired_media` a saved image URL that
    expired before it was read, so none says anything about the event.
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
            produced_live = False
            try:
                update, produced_live = make_update(source, record, cached, prior, meta, now, stats=stats)
            except (Exception, SystemExit) as exc:
                if not stop_on_error:
                    raise
                update = {"source_key": source["source_key"], "origin": "instagram",
                          "assessment": {"status": "error", "retryable": True,
                                         "error": f"{type(exc).__name__}: {exc}"},
                          "rows": [], "known_event_ids": []}
            if update is None and produced_live:
                streak = 0
            if update is not None:
                updates.append(update)
                failure = update.get("assessment") or {}
                if not (stop_on_error and failure.get("status") == "error"
                        and failure.get("retryable") is not False):
                    # Cached decisions say nothing about service recovery.
                    # A fresh response (even a grounding refusal) does.
                    if produced_live:
                        streak = 0
                    continue
                streak += 1
                if streak >= MAX_CONSECUTIVE_FAILURES:
                    log.error("Assessment stopped after %d failures in a row at %s: %s",
                              streak, source["source_key"], failure.get("error"))
                    break
                log.warning("Assessment failed for %s; continuing: %s", source["source_key"], failure.get("error"))
    if canonical is not None:
        updates = _withhold_reconciled(updates, registry, canonical, stats, reviews)
    return updates


def _withhold_reconciled(updates: list[dict], registry: dict, canonical: dict[str, dict],
                         stats: dict | None = None, reviews: Reviews | None = None) -> list[dict]:
    """Stop recreating repeat advertisements that reconciliation already merged.

    Reconciliation removes a duplicate and remaps its source onto the listing
    that survived. Republishing the same decision only recreates the duplicate
    until the next reconciliation removes it again. A source is withheld while
    its decision is unchanged, its canonical listing is live, and its row still
    matches that listing directly or through another withheld repeat. A changed
    decision, a missing listing, or a row that no longer matches publishes.

    A post listing several sessions withholds only the merged session and keeps
    publishing the rest, which ends its support for the merged listing. That is
    safe only while the listing survives without it: another post supports it,
    or it is locked. Otherwise the session republishes as before.

    A row an admin merged into the listing matches it whatever the rules say.
    """
    from reconcile_events import (Reviews, _CandidateIndex, _ambiguous_summaries,
                                  _summary_group_conflict, merge_duplicates,
                                  prefer_repost_source, same_event)
    reviews = reviews or Reviews()
    # Current decisions supersede saved rows when checking whether a summary
    # still identifies only one event. A newly collected competing event must
    # be considered even before its first publication.
    context = {**canonical, **{row['id']: row for update in updates for row in update.get('rows') or []}}
    source_index = _CandidateIndex(list(context.values()))
    ambiguous = _ambiguous_summaries(list(context.values()))
    supporters: dict[str, set[str]] = {}
    for key, record in registry.items():
        for event_id in record.get("event_ids") or []:
            supporters.setdefault(event_id, set()).add(key)
    pending: dict[str, list[dict]] = {}
    for update in updates:
        prior = registry.get(update["source_key"]) or {}
        if update["assessment"] != prior.get("assessment"):
            continue
        rows, supported = update.get("rows") or [], prior.get("event_ids") or []
        known = prior.get("known_event_ids") or []
        if len(rows) == 1:
            if (len(supported) == 1 and supported[0] in canonical
                    and rows[0]["id"] != supported[0] and rows[0]["id"] in known):
                pending.setdefault(supported[0], []).append(rows[0])
            continue
        media = update["source_key"].rsplit(":", 1)[-1]
        listings = [event_id for event_id in dict.fromkeys([*supported, *known])
                    if event_id in canonical and not _own_listing(event_id, media)
                    and (canonical[event_id].get("is_locked")
                         or supporters.get(event_id, set()) - {update["source_key"]})]
        for row in rows:
            if row["id"] in known and row["id"] not in supported:
                for event_id in listings:
                    pending.setdefault(event_id, []).append(row)
    withheld: dict[str, list[dict]] = {}
    skipped: set[str] = set()
    for canonical_id, candidates in pending.items():
        group = [canonical[canonical_id]]
        # A session that could belong to several listings joins the first.
        candidates = [row for row in candidates if row["id"] not in skipped | ambiguous]
        while joined := [row for row in candidates
                         if reviews.kept(row["id"]) in {member["id"] for member in group}
                         or (any(same_event(row, member) for member in group)
                             and not _summary_group_conflict([*group, row]))]:
            group.extend(joined)
            candidates = [row for row in candidates if row not in joined]
        withheld[canonical_id] = group[1:]
        skipped.update(row["id"] for row in group[1:])
    if stats is not None and skipped:
        stats["reconciled_duplicates_skipped"] = len(skipped)
    kept = []
    for update in updates:
        rows = update.get("rows") or []
        if rows and all(row["id"] in skipped for row in rows):
            continue
        # The canonical source republishes its own row every run. Keep what
        # reconciliation merged into it from these duplicates (free food, a
        # partner's signup, a missing end or image), or the merge is undone.
        # Hosts are left to reconciliation; publication does not write them.
        update["rows"] = [
            {key: value for key, value in merge_duplicates(row, [row, *withheld[row["id"]]]).items()
             if key != "hosts"} if withheld.get(row["id"]) else row
            for row in rows if row["id"] not in skipped]
        # Reapply source corrections from the saved announcements even when a
        # repeat was withheld, or past sessions no longer enter reconciliation.
        update['rows'] = [
            {key: value for key, value in prefer_repost_source(
                row, source_index.peers(row), reviews=reviews).items() if key != 'hosts'}
            if not canonical.get(row['id'], {}).get('is_locked') else row
            for row in update['rows']]
        kept.append(update)
    return kept


def _own_listing(event_id: str, media_id) -> bool:
    """Whether a listing is this post's own: its single event or one of its sessions."""
    match = POST_EVENT_ID.fullmatch(str(event_id))
    return bool(match) and match.group(2) == str(media_id)


def _lists_sessions(prior: dict) -> bool:
    result = (prior.get("assessment") or {}).get("result") or {}
    return len(result.get("occurrences") or []) > 1 or bool(result.get("schedule"))


def _canonical_listings(processed: list[tuple[dict, dict]], registry: dict) -> dict[str, dict]:
    """Saved replacements, plus competing listings for incomplete schedules."""
    wanted = set()
    incomplete_sessions = False
    for record, _ in processed:
        prior = registry.get(f"instagram:post:{record.get('media_id')}") or {}
        event_ids = prior.get("event_ids") or []
        if _lists_sessions(prior):
            # Once a merged session is withheld, the listing it was merged into
            # leaves this post's support but stays among its known IDs.
            event_ids = [*event_ids, *(prior.get("known_event_ids") or [])]
        replacements = {event_id for event_id in event_ids
                        if not _own_listing(event_id, record.get("media_id"))}
        wanted.update(replacements)
        if replacements and _lists_sessions(prior):
            from reconcile_events import _place_words
            result = (prior.get('assessment') or {}).get('result') or {}
            occurrences = [*(result.get('occurrences') or []), *([result['schedule']] if result.get('schedule') else [])]
            incomplete_sessions |= any(row.get('all_day') is True or not _place_words(row)
                                       for row in occurrences)
    if not wanted:
        return {}
    if incomplete_sessions:
        # A formerly unique match can become ambiguous as other accounts are
        # collected. Reading only old replacements would hide that competitor.
        from db import get_imported_events
        return {row['id']: row for row in get_imported_events()}
    from db import get_event_rows_by_ids
    return {row["id"]: row for row in get_event_rows_by_ids(sorted(wanted))}


def publish_posts(processed: list[tuple[dict, dict]], now: str, *, notify: bool,
                  meta: dict | None = None) -> None:
    stats: dict[str, int] = {}
    registry = load_registry()
    canonical = _canonical_listings(processed, registry)
    # Source corrections also need admin decisions before choosing between
    # independently collected posts that have not yet been reconciled.
    reviews = None
    if canonical or len(processed) > 1:
        from reconcile_events import load_reviews
        reviews, _ = load_reviews()
    updates = post_updates(processed, meta if meta is not None else load_account_meta(), now,
                           registry=registry, stats=stats, stop_on_error=True,
                           canonical=canonical, reviews=reviews)
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
    post_archive.hydrate_local_posts(archive=post_archive.ArchiveIndex())
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
        update, _ = make_update(source, raw, cached, registry.get(key), meta, now.isoformat(),
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
