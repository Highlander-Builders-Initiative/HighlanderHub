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
        self.client.requested_ids = list(values)
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
        self.requested_ids = []
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
        fake_client = FakeClient(existing=[{"event_id": "old"}])
        fake_db = types.SimpleNamespace(client=Mock(return_value=fake_client))

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

        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": "https://discord.test"}):
            with patch.dict(sys.modules, {"db": fake_db}):
                with patch.object(
                    self.discord_notify.requests,
                    "post",
                    return_value=types.SimpleNamespace(status_code=204),
                ) as post:
                    notified = self.discord_notify.notify_free_food_events(rows)

        self.assertEqual(1, notified)
        self.assertEqual(["old", "new"], fake_client.requested_ids)
        self.assertEqual(
            [{"event_id": "new", "kind": "free_food"}],
            fake_client.upserted,
        )
        self.assertEqual("event_id,kind", fake_client.on_conflict)
        post.assert_called_once()
        payload = post.call_args.kwargs["json"]
        self.assertIn("Pizza night", payload["content"])
        self.assertEqual({"parse": []}, payload["allowed_mentions"])

    def test_free_food_message_has_details(self) -> None:
        message = self.discord_notify.build_free_food_discord_message(
            {
                "id": "event-1",
                "title": "Bagel breakfast",
                "category": "free_food",
                "starts_at": "2026-05-21T16:00:00.000Z",
                "location": "Rivera Library",
                "host": "UCR Library",
            }
        )

        self.assertIn("Free food found on Highlander Hub", message)
        self.assertIn("Bagel breakfast", message)
        self.assertIn("Hosted by UCR Library", message)
        self.assertIn("Details: /events/event-1", message)


if __name__ == "__main__":
    unittest.main()
