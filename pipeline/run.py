"""Single entry point: scrape all sources -> extract -> normalize.

Each source is independent. A failure in one shouldn't kill the others, so
we log and keep going.

Stages:
  1. **Scrape** – fetch raw data from each source (Instagram stories,
     UCR Events) and write it to disk.
  2. **Extract** – run OCR + Vertex AI Gemini structured extraction on
     Instagram story images, upsert results into Supabase, and cache
     per-story outputs to avoid redundant API calls.  Note: this stage
     makes external API calls (Google Vision, Vertex AI Gemini) and incurs cost.
  3. **Normalize** – convert raw on-disk archives into canonical event
     rows and upsert them into Supabase. Normalization can reuse older raw
     data after a scrape failure, but stale-row reconciliation is enabled
     only for structured sources whose current scrape completed.

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
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import extract_stories
import highlander_link
import normalize
import normalize_events
import scrape
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
    except SystemExit:
        results.append(
            StageResult(name, False, time.monotonic() - started, "SystemExit")
        )
        raise
    except Exception as e:  # noqa: BLE001 — per-source isolation
        log.error("%s failed: %s", name, e, exc_info=True)
        results.append(
            StageResult(name, False, time.monotonic() - started, f"{type(e).__name__}: {e}")
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
    _safe("instagram.scrape", scrape.main, results)
    ucr_events_ok = _safe("ucr_events.scrape", ucr_events.main, results)
    highlander_link_ok = _safe("highlander_link.scrape", highlander_link.main, results)
    # Extraction and normalization always run using whatever is on disk.
    _safe("instagram.extract", extract_stories.main, results)
    _safe("instagram.normalize", normalize.main, results)
    # normalize_events handles both ucr_events and highlander_link.
    reconcile_prefixes = []
    if ucr_events_ok:
        reconcile_prefixes.append("ucr_events_")
    if highlander_link_ok:
        reconcile_prefixes.append("highlander_link_")
    _safe(
        "events.normalize",
        lambda: normalize_events.main(reconcile_prefixes),
        results,
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    started = time.monotonic()
    results: list[StageResult] = []
    try:
        _run_stages(results)
    finally:
        # A stage that calls sys.exit shouldn't cost us the summary.
        _report(results, time.monotonic() - started)
    if not all(r.ok for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
