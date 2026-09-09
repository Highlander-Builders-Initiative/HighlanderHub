"""Re-run content-kind classification over rows already in Supabase.

Classification happens at extraction time, so a change to classify.py only
affects future scrapes — rows written under the old rules keep their old kind
until something reclassifies them. This is that something.

Dry run by default; pass --apply to write. Rows with is_locked are never
touched — that is the same contract the scraper honors for manual corrections.

    python3 backfill_content_kind.py --to student_application
    python3 backfill_content_kind.py --to student_application --apply

Without --to, every disagreement is listed. Prefer scoping a backfill to the
kind the classifier change was about: an unscoped --apply also rewrites rows
that drifted for unrelated reasons (an earlier rule change, a hand edit made
before locking was routine), which is rarely what you want.

Only title/description/source are available on the stored row, so Localist
`audiences` are not in play here. That is the same input the pipeline uses for
instagram/manual origins, but it means a campus_website row can classify
differently than it did at import; rows whose kind was set by an audience
signal are left alone unless --include-audience-origins is passed.
"""
from __future__ import annotations

import argparse
import logging

from classify import classify_content_kind
from db import client

log = logging.getLogger("pipeline.backfill_content_kind")

# Origins whose classification depends on `audiences`, which the events table
# does not store. Reclassifying them from text alone would undo audience-based
# calls, so they are skipped unless explicitly requested.
AUDIENCE_ORIGINS = {"campus_website", "club_website"}


def plan(
    include_audience_origins: bool = False,
    to_kind: str | None = None,
) -> list[dict]:
    rows = (
        client()
        .table("events")
        .select("id,title,description,source,content_kind,is_locked")
        .eq("is_locked", False)
        .execute()
        .data
        or []
    )
    changes = []
    for row in rows:
        if (
            not include_audience_origins
            and row.get("source") in AUDIENCE_ORIGINS
        ):
            continue
        kind = classify_content_kind(
            row.get("source") or "",
            title=row.get("title") or "",
            description=row.get("description") or "",
        )
        if kind == row.get("content_kind"):
            continue
        if to_kind and kind != to_kind:
            continue
        changes.append({**row, "new_content_kind": kind})
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the changes")
    parser.add_argument(
        "--to",
        metavar="KIND",
        help="only rows whose new classification is KIND",
    )
    parser.add_argument(
        "--include-audience-origins",
        action="store_true",
        help="also reclassify campus_website/club_website rows",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    changes = plan(args.include_audience_origins, args.to)
    if not changes:
        log.info("No rows need reclassifying.")
        return

    for row in changes:
        log.info(
            "%s -> %s  %s  %s",
            row["content_kind"],
            row["new_content_kind"],
            row["source"],
            row["title"][:60],
        )
    log.info("%d row(s) affected.", len(changes))

    if not args.apply:
        log.info("Dry run. Re-run with --apply to write.")
        return

    for row in changes:
        client().table("events").update(
            {"content_kind": row["new_content_kind"]}
        ).eq("id", row["id"]).execute()
    log.info("Updated %d row(s).", len(changes))


if __name__ == "__main__":
    main()
