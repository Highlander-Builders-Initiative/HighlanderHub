"""Single entry point: Apify collection -> OCR -> assessment -> publication.

Each source is independent. A failure in one shouldn't kill the others, so
we log and keep going.

Stages:
  1. Collect Instagram feed posts through the Apify API.
  2. Extract cached post images with Google Vision OCR.
  3. Assess and publish the post archive even when collection failed.
  4. Reconcile corroborated events and send eligible free-food alerts.

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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import cached_property
from typing import Any

import assessed_events
import extract_posts
import reconcile_events
import apify_posts
from config import DATA_DIR, load_account_meta

log = logging.getLogger("pipeline.run")

RUN_HISTORY = DATA_DIR / "run_history.jsonl"


@dataclass
class StageResult:
    name: str
    ok: bool
    seconds: float
    error: str | None = None


@dataclass
class InstagramPosts:
    """Keep extracted posts available for publication."""

    posts: list[tuple[dict, dict]] = field(default_factory=list)
    cached_only: bool = False

    @cached_property
    def meta(self) -> dict[str, dict[str, Any]]:
        # A failed load remains retryable during publication.
        return load_account_meta()

    def extract_posts(self) -> None:
        self.posts, stats = extract_posts.extract_all(set(self.meta), cached_only=self.cached_only)
        if stats.get("stopped_at"):
            raise RuntimeError(f"Extraction stopped at {stats['stopped_at']}; completed posts retained")
        if stats.get("errors"):
            raise RuntimeError(f"Extraction failed for {stats['errors']} post(s) and continued past them; "
                               f"first: {stats['first_error']}")

    def publish(self) -> None:
        assessed_events.publish_posts(
            self.posts, datetime.now(timezone.utc).isoformat(),
            meta=self.meta, notify=False,
        )


def _safe(name: str, fn, results: list[StageResult]) -> bool:
    """Run one stage, record its outcome, and keep the pipeline going."""
    started = time.monotonic()
    try:
        fn()
    except KeyboardInterrupt:
        results.append(StageResult(name, False, time.monotonic() - started,
                                   "KeyboardInterrupt: interrupted; saved work retained for resume"))
        raise
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
        "resume": {
            "command": "pipeline/.venv/bin/python pipeline/run.py",
            "instructions": "Resolve the reported API/configuration error, then rerun. "
                            "Unfinished Apify batches resume without repeating completed batches. "
                            "A CollectionHalted stage stops paid batches on purpose and keeps "
                            "doing so until its cause is reviewed and apify_posts.py is rerun "
                            "with --resume-halted. "
                            "Post extractions and assessments reuse their saved caches.",
            "checkpoints": "Supabase instagram_post_checkpoints",
            "apify_plan": str(DATA_DIR / "apify_plan.json"),
        },
    }
    try:
        RUN_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with RUN_HISTORY.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        from post_archive import write_json
        write_json(RUN_HISTORY.with_name("last_run.json"), record)
    except OSError as e:
        log.warning("could not append to %s: %s", RUN_HISTORY, e)


def _report(results: list[StageResult], total_seconds: float) -> None:
    _log_summary(results, total_seconds)
    _write_history(results, total_seconds)


def _run_stages(results: list[StageResult]) -> None:
    # Apify failures do not invalidate already mirrored posts or their CDN URLs.
    # Continue OCR on the completed prefix even if dataset pagination stopped.
    _safe("instagram.posts.collect", apify_posts.main, results)
    posts = InstagramPosts()
    _safe("instagram.posts.extract", posts.extract_posts, results)
    _safe("instagram.publish", posts.publish, results)
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
