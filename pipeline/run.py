"""Single entry point: scrape all sources -> extract -> normalize.

Each source is independent. A failure in one shouldn't kill the others, so
we log and keep going.

Stages:
  1. **Structured scrape + normalize** – fetch Localist and HighlanderLink
     snapshots, then upsert them. This finishes before Instagram extract so a
     later Instagram timeout or `SystemExit` cannot strand a completed campus
     snapshot. Stale-row reconciliation is enabled only for sources whose
     current scrape completed.
  2. **Instagram story scrape** – fetch story JSON to disk.
  3. **Instagram post scrape** – fetch feed posts for the same accounts,
     forward-only from each account's activation timestamp.
  4. **Extract** – run OCR + Vertex AI Gemini structured extraction on
     Instagram story images and post carousels, caching per-item outputs to
     avoid redundant API calls. Stories and posts are separate stages so a
     failure in one channel is attributable; both read whatever is on disk, so
     a failed collection still publishes the archive it already has. Note:
     these stages make external API calls (Google Vision, Vertex AI Gemini)
     and incur cost.
  5. **Instagram publish** – assess both channels and reconcile their event
     support in one transaction, so a post and the stories resharing it settle
     on one listing instead of racing each other across two batches.
  6. **Instagram normalize** – rebuild `stories` rows from the on-disk
     archive. Posts never enter that table.
  7. **Reconcile events** – merge corroborated cross-source duplicates, then
     send eligible free-food alerts once the canonical listings are saved.

Every run ends with a per-stage summary — printed to the log and appended to
`data/run_history.jsonl`. Because stage failures are isolated, a dead source
still produces a working feed: without the summary the only signal is a
nonzero exit code, which is easy to attribute to whichever source broke last.
The history file answers "when did this stage last succeed?" without having to
reconstruct it from raw-file mtimes.
"""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import assessed_events
import extract_posts
import extract_stories
import highlander_link
import normalize
import normalize_events
import reconcile_events
import scrape
import scrape_posts
import ucr_events
from config import DATA_DIR

log = logging.getLogger("pipeline.run")

RUN_HISTORY = DATA_DIR / "run_history.jsonl"


@dataclass
class StageResult:
    name: str
    ok: bool
    seconds: float
    error: str | None = None


def _safe(name: str, fn, results: list[StageResult]) -> bool:
    """Run one stage, record its outcome, and keep the pipeline going."""
    started = time.monotonic()
    try:
        fn()
    except (Exception, SystemExit) as e:  # noqa: BLE001 — per-source isolation
        log.error("%s failed: %s", name, e, exc_info=True)
        results.append(
            StageResult(
                name, False, time.monotonic() - started, f"{type(e).__name__}: {e}"
            )
        )
        return False
    results.append(StageResult(name, True, time.monotonic() - started))
    return True


def _log_summary(results: list[StageResult], total_seconds: float) -> None:
    if not results:
        log.error("run summary: no stages ran")
        return

    width = max(len(r.name) for r in results)
    log.info("---- run summary ----")
    for r in results:
        log.info(
            "  %-*s  %-6s %6.1fs%s",
            width,
            r.name,
            "ok" if r.ok else "FAILED",
            r.seconds,
            f"  {r.error}" if r.error else "",
        )

    failed = [r.name for r in results if not r.ok]
    if failed:
        log.error(
            "run FAILED in %.1fs — %d of %d stages broken: %s",
            total_seconds,
            len(failed),
            len(results),
            ", ".join(failed),
        )
    else:
        log.info("run ok in %.1fs — %d stages", total_seconds, len(results))


def _write_history(results: list[StageResult], total_seconds: float) -> None:
    """Append one JSON line per run. Best-effort: never break a run over it."""
    record = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "ok": all(r.ok for r in results),
        "seconds": round(total_seconds, 1),
        "stages": [
            {
                "name": r.name,
                "ok": r.ok,
                "seconds": round(r.seconds, 1),
                **({"error": r.error} if r.error else {}),
            }
            for r in results
        ],
    }
    try:
        RUN_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with RUN_HISTORY.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        log.warning("could not append to %s: %s", RUN_HISTORY, e)


def _report(results: list[StageResult], total_seconds: float) -> None:
    _log_summary(results, total_seconds)
    _write_history(results, total_seconds)


def _run_stages(results: list[StageResult]) -> None:
    ucr_events_ok = _safe("ucr_events.scrape", ucr_events.main, results)
    highlander_link_ok = _safe("highlander_link.scrape", highlander_link.main, results)
    reconcile_prefixes = []
    if ucr_events_ok:
        reconcile_prefixes.append("ucr_events_")
    if highlander_link_ok:
        reconcile_prefixes.append("highlander_link_")
    _safe(
        "events.normalize",
        lambda: normalize_events.main(reconcile_prefixes, notify=False),
        results,
    )
    # Instagram extract/publish/normalize always run using whatever is on disk,
    # so a collection failure costs coverage but never the existing feed.
    _safe("instagram.scrape", scrape.main, results)
    _safe("instagram.posts.scrape", scrape_posts.main, results)

    # Extraction fills these in; publication settles both channels together.
    # Held across stages rather than returned, so a failed extract still lets
    # the other channel publish whatever it read.
    channels: dict[str, Any] = {"meta": {}, "stories": [], "posts": []}

    def extract_stories_stage() -> None:
        channels["meta"] = extract_stories._load_account_meta()
        channels["stories"] = extract_stories.extract_all(channels["meta"])

    def extract_posts_stage() -> None:
        if not channels["meta"]:
            channels["meta"] = extract_stories._load_account_meta()
        channels["posts"] = extract_posts.extract_all(set(channels["meta"]))[0]

    def publish_instagram_stage() -> None:
        if not channels["meta"]:
            channels["meta"] = extract_stories._load_account_meta()
        assessed_events.publish_instagram(
            channels["stories"], channels["posts"], channels["meta"],
            datetime.now(timezone.utc).isoformat(), notify=False,
        )

    _safe("instagram.extract", extract_stories_stage, results)
    _safe("instagram.posts.extract", extract_posts_stage, results)
    _safe("instagram.publish", publish_instagram_stage, results)
    _safe("instagram.normalize", normalize.main, results)
    _safe("events.reconcile", reconcile_events.main, results)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    started = time.monotonic()
    results: list[StageResult] = []
    try:
        _run_stages(results)
    finally:
        # KeyboardInterrupt / unexpected abort still gets a summary.
        _report(results, time.monotonic() - started)
    if not all(r.ok for r in results):
        sys.exit(1)


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), RotatingFileHandler(DATA_DIR / "run.log", maxBytes=5_000_000, backupCount=1)],
    )
    main()
