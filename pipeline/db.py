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
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

log = logging.getLogger("pipeline.db")


def client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise SystemExit(
            "Supabase env missing. Set SUPABASE_URL and SUPABASE_SERVICE_KEY "
            "in pipeline/.env."
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


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
