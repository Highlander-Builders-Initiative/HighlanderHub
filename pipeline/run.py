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
"""
from __future__ import annotations

import logging
import sys

import extract_stories
import highlander_link
import normalize
import normalize_events
import scrape
import ucr_events

log = logging.getLogger("pipeline.run")


def _safe(name: str, fn) -> bool:
    try:
        fn()
        return True
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 — per-source isolation
        log.error("%s failed: %s", name, e, exc_info=True)
        return False


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ok = True
    ok &= _safe("instagram.scrape", scrape.main)
    ucr_events_ok = _safe("ucr_events.scrape", ucr_events.main)
    highlander_link_ok = _safe("highlander_link.scrape", highlander_link.main)
    ok &= ucr_events_ok
    ok &= highlander_link_ok
    # Extraction and normalization always run using whatever is on disk.
    ok &= _safe("instagram.extract", extract_stories.main)
    ok &= _safe("instagram.normalize", normalize.main)
    # normalize_events handles both ucr_events and highlander_link.
    reconcile_prefixes = []
    if ucr_events_ok:
        reconcile_prefixes.append("ucr_events_")
    if highlander_link_ok:
        reconcile_prefixes.append("highlander_link_")
    ok &= _safe(
        "events.normalize",
        lambda: normalize_events.main(reconcile_prefixes),
    )
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
