"""Supabase client + upsert helpers for the pipeline.

Reads SUPABASE_URL and SUPABASE_SERVICE_KEY from pipeline/.env (gitignored).
Uses the service_role key, which bypasses RLS — required for the pipeline
to write to tables whose policies only allow public reads.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Iterable

from dotenv import load_dotenv
from supabase import Client, create_client

from config import ROOT

load_dotenv(ROOT / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get(
    "SUPABASE_SERVICE_ROLE_KEY"
)

log = logging.getLogger("pipeline.db")


_client: Client | None = None


def client() -> Client:
    # Reuse one client across the whole run so HTTP connections (and TLS
    # handshakes) are pooled instead of rebuilt on every call.
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise SystemExit(
                "Supabase env missing. Set SUPABASE_URL and SUPABASE_SERVICE_KEY "
                "in pipeline/.env."
            )
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def upsert_batched(
    table: str,
    rows: Iterable[dict[str, Any]],
    on_conflict: str = "id",
    batch_size: int = 200,
) -> int:
    """Upsert rows in batches. Returns total count written."""
    c = client()
    rows = list(rows)
    total = 0
    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        c.table(table).upsert(chunk, on_conflict=on_conflict).execute()
        total += len(chunk)
        log.info("%s: upserted %d/%d", table, total, len(rows))
    return total


def delete_rows_by_ids(
    table: str,
    ids: Iterable[str],
    batch_size: int = 200,
) -> int:
    """Delete rows by primary id in batches. Returns total count requested."""
    c = client()
    ids = list(dict.fromkeys(ids))
    total = 0
    for i in range(0, len(ids), batch_size):
        chunk = ids[i : i + batch_size]
        c.table(table).delete().in_("id", chunk).execute()
        total += len(chunk)
        log.info("%s: deleted %d/%d stale rows", table, total, len(ids))
    return total


def delete_rows_by_prefix(table: str, prefix: str) -> int:
    """Delete rows whose id starts with the given prefix."""
    c = client()
    pattern = f"{prefix}%"
    existing = c.table(table).select("id").like("id", pattern).execute()
    count = len(getattr(existing, "data", None) or [])
    if count:
        c.table(table).delete().like("id", pattern).execute()
        log.info("%s: deleted %d rows with id prefix %s", table, count, prefix)
    return count


def delete_events_missing_from_ids(
    id_prefixes: Iterable[str],
    keep_ids: Iterable[str],
    batch_size: int = 200,
) -> int:
    """Delete unlocked imported events under prefixes that are absent this run."""
    c = client()
    keep = {str(event_id) for event_id in keep_ids}
    stale_ids: list[str] = []

    for prefix in dict.fromkeys(id_prefixes):
        existing = (
            c.table("events")
            .select("id,is_locked")
            .like("id", f"{prefix}%")
            .execute()
        )
        for row in getattr(existing, "data", []) or []:
            event_id = str(row.get("id") or "")
            if not event_id or row.get("is_locked") or event_id in keep:
                continue
            stale_ids.append(event_id)

    return delete_rows_by_ids("events", stale_ids, batch_size=batch_size)


def get_deleted_event_ids() -> set[str]:
    """Return admin-deleted event IDs that pipeline imports must not recreate."""
    res = client().table("deleted_events").select("event_id").execute()
    return {
        str(row["event_id"])
        for row in getattr(res, "data", []) or []
        if row.get("event_id")
    }
