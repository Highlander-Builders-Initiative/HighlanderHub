from __future__ import annotations

import importlib
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception
    fake_requests.post = Mock()
    sys.modules["requests"] = fake_requests


class FakeTable:
    def __init__(self, client: "FakeClient") -> None:
        self.client = client
        self.mode = "select"

    def select(self, *_args):
        self.mode = "select"
        return self

    def eq(self, *_args):
        return self

    def in_(self, _column, values):
        self.client.requests.append((_column, list(values)))
        return self

    def upsert(self, rows, on_conflict=None):
        self.mode = "upsert"
        self.client.upserted = rows
        self.client.on_conflict = on_conflict
        return self

    def execute(self):
        if self.mode == "upsert":
            return types.SimpleNamespace(data=self.client.upserted)
        return types.SimpleNamespace(data=self.client.existing)


class FakeClient:
    def __init__(self, existing):
        self.existing = existing
        self.requests = []
        self.upserted = []
        self.on_conflict = None

    def table(self, name):
        assert name == "discord_notifications"
        return FakeTable(self)


class DiscordNotifyTests(unittest.TestCase):
    def setUp(self) -> None:
        sys.modules.pop("discord_notify", None)
        self.discord_notify = importlib.import_module("discord_notify")

    def tearDown(self) -> None:
        sys.modules.pop("discord_notify", None)

    def test_free_food_notifications_skip_ledgered_events(self) -> None:
        rows = [
            {
                "id": "old",
                "title": "Already sent",
                "category": "free_food",
                "starts_at": "2026-05-21T01:00:00.000Z",
            },
            {
                "id": "new",
                "title": "Pizza night",
                "category": "free_food",
                "starts_at": "2026-05-21T02:00:00.000Z",
                "location": "HUB 302",
                "host": "ACM at UCR",
                "source_url": "https://events.ucr.edu/pizza",
            },
            {
                "id": "social",
                "title": "Mixer",
                "category": "social",
            },
        ]
        old_key = self.discord_notify.free_food_notification_key(rows[0])
        new_key = self.discord_notify.free_food_notification_key(rows[1])
        fake_client = FakeClient(existing=[{"notification_key": old_key}])
        fake_db = types.SimpleNamespace(client=Mock(return_value=fake_client))

        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": "https://discord.test"}):
            with patch.dict(sys.modules, {"db": fake_db}):
                with patch.object(
                    self.discord_notify.requests,
                    "post",
                    return_value=types.SimpleNamespace(status_code=204),
                ) as post:
                    notified = self.discord_notify.notify_free_food_events(rows)

        self.assertEqual(1, notified)

        self.assertEqual(
            [
                ("notification_key", [old_key, new_key]),
                ("event_id", ["old", "new"]),
            ],
            fake_client.requests,
        )
        self.assertEqual(
            [
                {
                    "event_id": "new",
                    "kind": "free_food",
                    "notification_key": new_key,
                }
            ],
            fake_client.upserted,
        )
        self.assertEqual("kind,notification_key", fake_client.on_conflict)
        post.assert_called_once()
        payload = post.call_args.kwargs["json"]
        self.assertIn("Pizza night", payload["content"])
        self.assertIn("Where: HUB 302", payload["content"])
        self.assertEqual({"parse": []}, payload["allowed_mentions"])

    def test_free_food_notifications_skip_same_event_with_new_row_id(self) -> None:
        replacement_row = {
            "id": "new-generated-id",
            "title": "Pizza night",
            "category": "club",
            "has_free_food": True,
            "starts_at": "2026-05-21T02:30:00.000Z",
            "location": "HUB 302",
            "host": "ACM at UCR",
        }
        key = self.discord_notify.free_food_notification_key(replacement_row)
        fake_client = FakeClient(existing=[{"notification_key": key}])
        fake_db = types.SimpleNamespace(client=Mock(return_value=fake_client))

        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": "https://discord.test"}):
            with patch.dict(sys.modules, {"db": fake_db}):
                with patch.object(self.discord_notify.requests, "post") as post:
                    notified = self.discord_notify.notify_free_food_events(
                        [replacement_row]
                    )

        self.assertEqual(0, notified)
        self.assertEqual(
            [
                ("notification_key", [key]),
                ("event_id", ["new-generated-id"]),
            ],
            fake_client.requests,
        )
        self.assertEqual([], fake_client.upserted)
        post.assert_not_called()

    def test_free_food_notifications_skip_duplicate_keys_in_same_run(self) -> None:
        rows = [
            {
                "id": "structured-id",
                "title": "Taco Social",
                "category": "club",
                "has_free_food": True,
                "starts_at": "2026-05-21T02:00:00.000Z",
            },
            {
                "id": "ig-id",
                "title": "Taco Social",
                "category": "social",
                "has_free_food": True,
                "starts_at": "2026-05-21T04:00:00.000Z",
            },
        ]
        fake_client = FakeClient(existing=[])
        fake_db = types.SimpleNamespace(client=Mock(return_value=fake_client))

        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": "https://discord.test"}):
            with patch.dict(sys.modules, {"db": fake_db}):
                with patch.object(
                    self.discord_notify.requests,
                    "post",
                    return_value=types.SimpleNamespace(status_code=204),
                ) as post:
                    notified = self.discord_notify.notify_free_food_events(rows)

        self.assertEqual(1, notified)
        post.assert_called_once()
        self.assertEqual(1, len(fake_client.upserted))

    def test_free_food_message_has_details(self) -> None:
        message = self.discord_notify.build_free_food_discord_message(
            {
                "id": "event-1",
                "title": "Bagel breakfast",
                "category": "free_food",
                "starts_at": "2026-05-21T16:00:00.000Z",
                "location": "Rivera Library",
                "host": "UCR Library",
                "source_url": "https://www.instagram.com/stories/ucrlibrary/1/",
            }
        )

        self.assertIn("Free food on campus", message)
        self.assertIn("Bagel breakfast", message)
        self.assertIn("Host: UCR Library", message)
        self.assertIn("Details: https://highlanderhub.app/events/event-1", message)
        self.assertNotIn("Source:", message)
        self.assertNotIn("instagram.com", message)


if __name__ == "__main__":
    unittest.main()
