"""Single entry point: scrape all sources -> extract -> normalize.

Each source is independent. A failure in one shouldn't kill the others, so
we log and keep going.

Stages:
  1. Scrape and normalize Localist and HighlanderLink independently.
  2. Collect Instagram feed posts, respecting the persisted collection cooldown.
  3. Extract cached post images with Google Vision OCR.
  4. Assess and publish the post archive even when collection failed.
  5. Reconcile corroborated events and send eligible free-food alerts.

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
import highlander_link
import normalize_events
import reconcile_events
import scrape_posts
import ucr_events
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

    @cached_property
    def meta(self) -> dict[str, dict[str, Any]]:
        # A failed load remains retryable during publication.
        return load_account_meta()

    def extract_posts(self) -> None:
        self.posts, _ = extract_posts.extract_all(set(self.meta))

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
    # Extraction and publication still process the archive after collection fails.
    _safe("instagram.posts.scrape", scrape_posts.main, results)

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
