"""Discord webhook notifications for pipeline-discovered events."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests

log = logging.getLogger("pipeline.discord_notify")

MESSAGE_LIMIT = 1900
PACIFIC_TZ = ZoneInfo("America/Los_Angeles")


def _text(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _format_when(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "Time TBD"
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return "Time TBD"
    return dt.astimezone(PACIFIC_TZ).strftime("%a, %b %d, %I:%M %p").replace(
        " 0", " "
    )


def _compact(parts: Iterable[str | None]) -> str:
    return "\n".join(part for part in parts if part)[:MESSAGE_LIMIT]


def build_free_food_discord_message(row: dict[str, Any]) -> str:
    event_id = _text(row.get("id"))
    title = _text(row.get("title"), "Untitled event")
    host = _text(row.get("host"))
    location = _text(row.get("location"))
    link = _text(row.get("source_url")) or (f"/events/{event_id}" if event_id else "")

    return _compact(
        [
            "Free food found on Highlander Hub",
            f"**{title}**",
            _format_when(row.get("starts_at")),
            host and f"Hosted by {host}",
            location or None,
            link and f"Details: {link}",
        ]
    )


def _post_discord_message(content: str) -> bool:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return False

    try:
        response = requests.post(
            webhook_url,
            json={"content": content, "allowed_mentions": {"parse": []}},
            timeout=10,
        )
    except requests.RequestException as exc:
        log.warning("Discord webhook failed: %s", exc)
        return False

    if response.status_code >= 400:
        log.warning("Discord webhook failed with status %s", response.status_code)
        return False
    return True


def notify_free_food_events(rows: Iterable[dict[str, Any]]) -> int:
    if not os.environ.get("DISCORD_WEBHOOK_URL"):
        return 0

    candidates = [
        row
        for row in rows
        if row.get("category") == "free_food" and _text(row.get("id"))
    ]
    if not candidates:
        return 0

    ids = [_text(row.get("id")) for row in candidates]
    try:
        from db import client

        db_client = client()
        existing_res = (
            db_client.table("discord_notifications")
            .select("event_id")
            .eq("kind", "free_food")
            .in_("event_id", ids)
            .execute()
        )
        existing = {
            str(row["event_id"])
            for row in getattr(existing_res, "data", []) or []
            if row.get("event_id")
        }
    except Exception as exc:  # noqa: BLE001 - notifications must not fail ingest.
        log.warning("Could not read Discord notification ledger: %s", exc)
        return 0

    sent = []
    for row in candidates:
        event_id = _text(row.get("id"))
        if event_id in existing:
            continue
        if _post_discord_message(build_free_food_discord_message(row)):
            sent.append({"event_id": event_id, "kind": "free_food"})

    if not sent:
        return 0

    try:
        db_client.table("discord_notifications").upsert(
            sent,
            on_conflict="event_id,kind",
        ).execute()
    except Exception as exc:  # noqa: BLE001 - avoid retry-blocking the pipeline.
        log.warning("Could not write Discord notification ledger: %s", exc)

    return len(sent)
