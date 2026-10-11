"""Gradual cleanup of finished events and their unreferenced flyer files.

Runs before extraction to free upload space. Failures are reported separately
by run.py and never prevent collection, extraction or publication.
"""
from __future__ import annotations

import argparse
import logging

from db import client

log = logging.getLogger("pipeline.event_retention")


def main(*, dry_run: bool = False) -> dict:
    c = client()
    retired = 0 if dry_run else c.rpc("retire_old_events").execute().data
    candidates = c.rpc("old_event_flyers").execute().data or []
    # Do not clear OCR/cache URLs: unchanged posts reuse those caches without
    # uploading their retired images again. New/edited sources still extract.
    removed = 0
    if candidates and not dry_run:
        names = [row["name"] for row in candidates]
        response = c.storage.from_("event-flyers").remove(names)
        removed = len(response)
        if removed != len(names):
            raise RuntimeError(f"Storage removed {removed}/{len(names)} flyers; remaining files retry next run")
    result = {"retired_events": retired, "eligible_flyers": len(candidates),
              "removed_flyers": removed, "bytes": sum(row["bytes"] for row in candidates),
              "dry_run": dry_run}
    log.info("Event retention: %s", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Only inspect eligible files; delete nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    main(dry_run=args.dry_run)
