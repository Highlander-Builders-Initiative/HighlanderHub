"""Fail the run while the Supabase project still has room under its plan limits.

The Free plan restricts a project (every API call returns 402) once it exceeds
500 MB of database or 1 GB of file storage. In November 2026 storage reached
3.1 GB with nothing reporting it, and the site lost its data. This stage reads
both sizes each run and fails at WARN_FRACTION of a limit, which marks the
workflow run failed and sends GitHub's failure email while there is still
time to clean up.

Egress (5 GB uncached per month) cannot be read from the database; check it
on the project's Usage page.
"""
from __future__ import annotations

import logging

log = logging.getLogger("pipeline.project_usage")

# Supabase Free plan quotas (supabase.com/pricing, checked 2026-11-17).
DATABASE_LIMIT_BYTES = 500 * 1024 * 1024
STORAGE_LIMIT_BYTES = 1024 * 1024 * 1024
WARN_FRACTION = 0.8


def check(usage: dict) -> dict:
    """Usage with each share of its limit; raises once any share reaches WARN_FRACTION."""
    report = {
        "database_mb": round(usage["database_bytes"] / 1024 / 1024, 1),
        "database_share": round(usage["database_bytes"] / DATABASE_LIMIT_BYTES, 3),
        "storage_mb": round(usage["storage_bytes"] / 1024 / 1024, 1),
        "storage_share": round(usage["storage_bytes"] / STORAGE_LIMIT_BYTES, 3),
        "storage_files": usage["storage_files"],
    }
    log.info("Supabase usage: %s", report)
    over = [name for name in ("database", "storage") if report[f"{name}_share"] >= WARN_FRACTION]
    if over:
        raise RuntimeError(
            f"Supabase {' and '.join(over)} at {WARN_FRACTION:.0%}+ of the Free plan limit: {report}. "
            "Clean up before it is exceeded; an exceeded quota restricts the whole project.")
    return report


def main() -> dict:
    from db import client

    rows = client().rpc("project_usage").execute().data or []
    if not rows:
        raise RuntimeError("project_usage() returned nothing")
    return check(rows[0])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
