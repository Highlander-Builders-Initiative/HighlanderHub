"""Discord webhook notifications for pipeline-discovered events."""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

log = logging.getLogger("pipeline.discord_notify")

MESSAGE_LIMIT = 1900
SITE_URL = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://highlanderhub.app").rstrip("/")
_WHITESPACE = re.compile(r"\s+")

try:
    PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
except ZoneInfoNotFoundError:  # pragma: no cover - Windows without tzdata.
    PACIFIC_TZ = timezone(timedelta(hours=-7), "America/Los_Angeles")


def _text(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _format_when(value: Any) -> str:
    dt = _parse_instant(value)
    if dt is None:
        return "Time TBD"
    return dt.astimezone(PACIFIC_TZ).strftime("%a, %b %d, %I:%M %p").replace(
        " 0", " "
    )


def _parse_instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt


def _key_text(value: Any) -> str:
    return _WHITESPACE.sub(" ", str(value or "").casefold()).strip()


def _canonical_url(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            "",
            "",
        )
    )


def free_food_notification_key(row: dict[str, Any]) -> str:
    """Durable identity for a free-food alert across scraper row ID changes."""
    title = _key_text(row.get("title"))
    starts_at = _parse_instant(row.get("starts_at"))
    if title and starts_at is not None:
        local_day = starts_at.astimezone(PACIFIC_TZ).strftime("%Y%m%d")
        return f"free_food:v2:title-day:{title}|{local_day}"

    source_url = _canonical_url(row.get("source_url"))
    if source_url:
        return f"free_food:v2:url:{source_url}"

    event_id = _text(row.get("id"))
    return f"free_food:v2:id:{event_id}"


def _compact(parts: Iterable[str | None]) -> str:
    return "\n".join(part for part in parts if part)[:MESSAGE_LIMIT]


def build_free_food_discord_message(row: dict[str, Any]) -> str:
    event_id = _text(row.get("id"))
    title = _text(row.get("title"), "Untitled event")
    host = _text(row.get("host"))
    location = _text(row.get("location"))
    event_link = f"{SITE_URL}/events/{event_id}" if event_id else ""
    source_link = _text(row.get("source_url"))
    link = event_link or source_link

    return _compact(
        [
            "Free food on campus",
            f"**{title}**",
            _format_when(row.get("starts_at")),
            location and f"Where: {location}",
            host and f"Host: {host}",
            link and f"Details: {link}",
            source_link and source_link != link and f"Source: {source_link}",
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
        if (row.get("has_free_food") or row.get("category") == "free_food")
        and _text(row.get("id"))
    ]
    if not candidates:
        return 0

    notification_keys = [free_food_notification_key(row) for row in candidates]
    event_ids = [_text(row.get("id")) for row in candidates]
    try:
        from db import client

        db_client = client()
        existing_keys_res = (
            db_client.table("discord_notifications")
            .select("notification_key")
            .eq("kind", "free_food")
            .in_("notification_key", notification_keys)
            .execute()
        )
        existing_ids_res = (
            db_client.table("discord_notifications")
            .select("event_id")
            .eq("kind", "free_food")
            .in_("event_id", event_ids)
            .execute()
        )
        existing_keys = {
            str(row["notification_key"])
            for row in getattr(existing_keys_res, "data", []) or []
            if row.get("notification_key")
        }
        existing_ids = {
            str(row["event_id"])
            for row in getattr(existing_ids_res, "data", []) or []
            if row.get("event_id")
        }
    except Exception as exc:  # noqa: BLE001 - notifications must not fail ingest.
        log.warning("Could not read Discord notification ledger: %s", exc)
        return 0

    sent = []
    queued_keys = set(existing_keys)
    for row in candidates:
        event_id = _text(row.get("id"))
        notification_key = free_food_notification_key(row)
        if notification_key in queued_keys or event_id in existing_ids:
            continue
        if _post_discord_message(build_free_food_discord_message(row)):
            queued_keys.add(notification_key)
            sent.append(
                {
                    "event_id": event_id,
                    "kind": "free_food",
                    "notification_key": notification_key,
                }
            )

    if not sent:
        return 0

    try:
        db_client.table("discord_notifications").upsert(
            sent,
            on_conflict="kind,notification_key",
        ).execute()
    except Exception as exc:  # noqa: BLE001 - avoid retry-blocking the pipeline.
        log.warning("Could not write Discord notification ledger: %s", exc)

    return len(sent)
