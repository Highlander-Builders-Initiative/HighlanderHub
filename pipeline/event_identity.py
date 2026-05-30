"""Shared event identity helpers for pipeline import rows."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

_WHITESPACE = re.compile(r"\s+")


def _parse_instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def event_key(row: dict[str, Any]) -> str | None:
    """Stable key for the same public event appearing from multiple sources."""
    title = _WHITESPACE.sub(" ", str(row.get("title") or "").casefold()).strip()
    starts_at = _parse_instant(row.get("starts_at"))
    if not title or starts_at is None:
        return None
    return f"{title}|{starts_at.strftime('%Y%m%dT%H%MZ')}"


def _row_score(row: dict[str, Any]) -> tuple[int, int, int, int, int, int, str]:
    description = str(row.get("description") or "")
    host = str(row.get("host") or "").strip()
    return (
        1 if row.get("category") == "free_food" else 0,
        1 if row.get("source") != "instagram" else 0,
        1 if host else 0,
        len(description),
        1 if row.get("image_url") else 0,
        1 if row.get("source_url") else 0,
        str(row.get("id") or ""),
    )


def dedupe_event_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupe imported events by exact id first, then same title/start."""
    by_id: dict[str, dict[str, Any]] = {}
    no_id: list[dict[str, Any]] = []
    for row in rows:
        row_id = row.get("id")
        if not row_id:
            no_id.append(row)
            continue
        existing = by_id.get(str(row_id))
        if existing is None or _row_score(row) >= _row_score(existing):
            by_id[str(row_id)] = row

    by_key: dict[str, dict[str, Any]] = {}
    out: list[dict[str, Any]] = []
    for row in [*by_id.values(), *no_id]:
        key = event_key(row)
        if key is None:
            out.append(row)
            continue
        existing = by_key.get(key)
        if existing is None or _row_score(row) >= _row_score(existing):
            by_key[key] = row

    return [*out, *by_key.values()]


def suppress_tombstoned_event_groups(
    rows: list[dict[str, Any]],
    tombstoned_ids: set[str],
) -> list[dict[str, Any]]:
    """Remove exact tombstoned ids and same-title/start duplicate siblings."""
    if not rows or not tombstoned_ids:
        return rows

    tombstoned_keys = {
        key
        for row in rows
        if str(row.get("id") or "") in tombstoned_ids
        if (key := event_key(row)) is not None
    }
    if not tombstoned_keys:
        return [
            row
            for row in rows
            if str(row.get("id") or "") not in tombstoned_ids
        ]

    return [
        row
        for row in rows
        if str(row.get("id") or "") not in tombstoned_ids
        and event_key(row) not in tombstoned_keys
    ]
