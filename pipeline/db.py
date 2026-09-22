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


def get_deleted_event_ids() -> set[str]:
    """Return admin-deleted event IDs that pipeline imports must not recreate."""
    found: set[str] = set()
    for offset in range(0, 1_000_000, 1000):
        batch = (
            client().table("deleted_events").select("event_id")
            .order("event_id").range(offset, offset + 999).execute().data or []
        )
        found.update(str(row["event_id"]) for row in batch if row.get("event_id"))
        if len(batch) < 1000:
            return found
    raise RuntimeError("Deleted event pagination exceeded its safety limit")


def get_imported_events() -> list[dict[str, Any]]:
    """Read all imported rows with stable pagination, including admin locks."""
    rows = []
    for offset in range(0, 1_000_000, 1000):
        batch = client().table("events").select("*").order("id").range(offset, offset+999).execute().data or []
        rows.extend(row for row in batch if str(row.get("id", "")).startswith("ig_"))
        if len(batch) < 1000:
            return rows
    raise RuntimeError("Imported event pagination exceeded its safety limit")


def get_event_rows_by_ids(
    ids: Iterable[str],
    batch_size: int = 200,
) -> list[dict[str, Any]]:
    """Return the event rows that currently exist for the requested IDs."""
    event_ids = list(dict.fromkeys(str(event_id) for event_id in ids if event_id))
    if not event_ids:
        return []
    c = client()
    rows: list[dict[str, Any]] = []
    for i in range(0, len(event_ids), batch_size):
        rows.extend(
            c.table("events")
            .select("*")
            .in_("id", event_ids[i : i + batch_size])
            .execute()
            .data
            or []
        )
    return rows
