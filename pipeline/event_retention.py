"""Gradual cleanup of finished events and unused flyer files.

Runs before extraction to free upload space. Failures are reported separately
by run.py and never prevent collection, extraction or publication.

A flyer file is unused when no listing points at it and no live event comes
from its post (see unused_event_flyers in the 20261114010000 migration). Each
event shows one slide, so most stored slides become unused once their post is
assessed; a later assessment that picks a deleted slide uploads it again at
publication.
"""
from __future__ import annotations

import argparse
import logging

from db import client
from image_ocr import DURABLE_FLYER_BUCKET

log = logging.getLogger("pipeline.event_retention")

# The Storage API removes a list of paths per request; the listing function
# returns at most 1000 rows per call.
BATCH_SIZE = 500
# Bounds the stage's runtime. A backlog clears over successive runs.
MAX_FLYERS_PER_RUN = 3000


def main(*, dry_run: bool = False, max_flyers: int = MAX_FLYERS_PER_RUN) -> dict:
    c = client()
    retired = 0 if dry_run else c.rpc("retire_old_events").execute().data
    # Do not clear OCR/cache URLs: unchanged posts reuse those caches without
    # uploading their retired images again. New/edited sources still extract,
    # and publication re-uploads a missing flyer an event comes to need.
    eligible = removed = removed_bytes = eligible_bytes = 0
    while eligible < max_flyers:
        size = min(BATCH_SIZE, max_flyers - eligible)
        batch = c.rpc("unused_event_flyers", {"max_rows": size}).execute().data or []
        eligible += len(batch)
        eligible_bytes += sum(row["bytes"] for row in batch)
        if dry_run or not batch:
            break
        names = [row["name"] for row in batch]
        response = c.storage.from_(DURABLE_FLYER_BUCKET).remove(names)
        removed += len(response)
        removed_bytes += sum(row["bytes"] for row in batch)
        if len(response) != len(names):
            raise RuntimeError(f"Storage removed {len(response)}/{len(names)} flyers; remaining files retry next run")
        if len(batch) < size:
            break
    result = {"retired_events": retired, "eligible_flyers": eligible,
              "removed_flyers": removed, "bytes": eligible_bytes,
              "removed_mb": round(removed_bytes / 1_000_000, 1), "dry_run": dry_run}
    log.info("Event retention: %s", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Only inspect eligible files; delete nothing")
    parser.add_argument("--max-flyers", type=int, default=MAX_FLYERS_PER_RUN,
                        help="Most flyer files to delete in this run")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    main(dry_run=args.dry_run, max_flyers=args.max_flyers)
