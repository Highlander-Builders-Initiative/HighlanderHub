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

EMBED_FIELD_LIMIT = 1024
EMBED_TITLE_LIMIT = 256
FREE_FOOD_EMBED_COLOR = 0x45B36B
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


def _event_link(row: dict[str, Any]) -> str:
    event_id = _text(row.get("id"))
    return f"{SITE_URL}/events/{event_id}" if event_id else ""


def _embed_field(name: str, value: str, inline: bool = True) -> dict[str, Any] | None:
    if not value:
        return None
    return {"name": name, "value": value[:EMBED_FIELD_LIMIT], "inline": inline}


def build_free_food_discord_embed(row: dict[str, Any]) -> dict[str, Any]:
    title = _text(row.get("title"), "Untitled event")
    host = _text(row.get("host"))
    location = _text(row.get("location"))
    fields = [
        field
        for field in [
            _embed_field("When", _format_when(row.get("starts_at"))),
            _embed_field("Where", location),
            _embed_field("Host", host),
        ]
        if field is not None
    ]

    embed: dict[str, Any] = {
        "author": {"name": "Free food on campus"},
        "title": title[:EMBED_TITLE_LIMIT],
        "color": FREE_FOOD_EMBED_COLOR,
        "footer": {"text": "Highlander Hub | Free food alert"},
    }
    event_link = _event_link(row)
    if event_link:
        embed["url"] = event_link
    if fields:
        embed["fields"] = fields
    return embed


def build_free_food_discord_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "embeds": [build_free_food_discord_embed(row)],
        "allowed_mentions": {"parse": []},
    }


def _post_discord_payload(payload: dict[str, Any]) -> bool:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return False

    try:
        response = requests.post(
            webhook_url,
            json=payload,
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
        if _post_discord_payload(build_free_food_discord_payload(row)):
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
