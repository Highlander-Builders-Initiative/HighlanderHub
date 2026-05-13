"""Single entry point: scrape all sources -> normalize.

Each source is independent. A failure in one shouldn't kill the others, so
we log and keep going. Normalization runs at the end regardless, since the
on-disk raw archive is the source of truth and may have data from earlier
runs even if today's fetch failed.
"""
from __future__ import annotations

import logging
import sys

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
    ok &= _safe("ucr_events.scrape", ucr_events.main)
    # Normalize always runs — uses whatever's on disk.
    _safe("instagram.normalize", normalize.main)
    _safe("ucr_events.normalize", normalize_events.main)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
