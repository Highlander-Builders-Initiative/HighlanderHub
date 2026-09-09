from __future__ import annotations

import importlib
import os
import sys
import types
import unittest
from datetime import datetime, timezone
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
        clock = patch.object(self.discord_notify, "datetime", wraps=datetime)
        self.clock = clock.start()
        self.clock.now.return_value = datetime(2026, 5, 20, tzinfo=timezone.utc)
        self.addCleanup(clock.stop)

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
        self.assertNotIn("content", payload)
        embed = payload["embeds"][0]
        fields = {field["name"]: field["value"] for field in embed["fields"]}
        self.assertEqual("Free food on campus", embed["author"]["name"])
        self.assertEqual("Pizza night", embed["title"])
        self.assertEqual("https://highlanderhub.app/events/new", embed["url"])
        self.assertEqual("HUB 302", fields["Where"])
        self.assertEqual("ACM at UCR", fields["Host"])
        self.assertNotIn("events.ucr.edu", str(payload))
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

    def test_free_food_payload_has_one_embedded_details_link(self) -> None:
        payload = self.discord_notify.build_free_food_discord_payload(
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

        embed = payload["embeds"][0]
        fields = {field["name"]: field["value"] for field in embed["fields"]}

        self.assertNotIn("content", payload)
        self.assertEqual("Free food on campus", embed["author"]["name"])
        self.assertEqual("Bagel breakfast", embed["title"])
        self.assertEqual("https://highlanderhub.app/events/event-1", embed["url"])
        self.assertEqual("Thu, May 21, 9:00 AM", fields["When"])
        self.assertEqual("Rivera Library", fields["Where"])
        self.assertEqual("UCR Library", fields["Host"])
        self.assertEqual("Highlander Hub | Free food alert", embed["footer"]["text"])
        self.assertNotIn("instagram.com", str(payload))

    def test_archived_events_never_reach_ledger_or_webhook(self) -> None:
        self.clock.now.return_value = datetime(2026, 9, 8, tzinfo=timezone.utc)
        rows = [
            {
                "id": f"archived-{day}",
                "title": f"Archived meal {day}",
                "has_free_food": True,
                "starts_at": f"2026-06-{day:02d}T17:00:00-07:00",
                "ends_at": f"2026-06-{day:02d}T19:00:00-07:00",
            }
            for day in range(1, 10)
        ]
        fake_db = types.SimpleNamespace(client=Mock(return_value=FakeClient(existing=[])))
        with (
            patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": "https://discord.test"}),
            patch.dict(sys.modules, {"db": fake_db}),
            patch.object(self.discord_notify.requests, "post", return_value=types.SimpleNamespace(status_code=204)) as post,
        ):
            self.assertEqual(0, self.discord_notify.notify_free_food_events(iter(rows)))
        fake_db.client.assert_not_called()
        post.assert_not_called()

    def test_notification_time_cutoffs(self) -> None:
        self.clock.now.return_value = datetime(2026, 9, 8, 19, tzinfo=timezone.utc)
        cases = [
            ("ended", "2026-09-08T10:00:00-07:00", "2026-09-08T11:59:59-07:00", False),
            ("ending now", "2026-09-08T10:00:00-07:00", "2026-09-08T12:00:00-07:00", False),
            ("ongoing", "2026-09-08T10:00:00-07:00", "2026-09-08T12:00:01-07:00", True),
            ("future", "2026-09-09T10:00:00-07:00", "2026-09-09T12:00:00-07:00", True),
            ("past without end", "2026-09-08T18:59:59Z", None, False),
            ("starting now without end", "2026-09-08T19:00:00Z", None, False),
            ("future without end", "2026-09-08T19:00:01Z", None, True),
            ("missing times", None, None, False),
            ("invalid start", "invalid", None, False),
            ("naive start", "2026-09-09T12:00:00", None, False),
            ("date only", "2026-09-09", None, False),
            ("invalid end", "2026-09-09T19:00:00Z", "invalid", False),
            ("naive end", "2026-09-09T19:00:00Z", "2026-09-09T20:00:00", False),
            ("empty end", "2026-09-09T19:00:00Z", "", False),
        ]
        rows = [
            {"id": name, "title": name, "category": "free_food", "starts_at": start, "ends_at": end}
            for name, start, end, _ in cases
        ]
        expected_ids = [name for name, _, _, eligible in cases if eligible]
        fake_client = FakeClient(existing=[])
        fake_db = types.SimpleNamespace(client=Mock(return_value=fake_client))
        with (
            patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": "https://discord.test"}),
            patch.dict(sys.modules, {"db": fake_db}),
            patch.object(self.discord_notify.requests, "post", return_value=types.SimpleNamespace(status_code=204)) as post,
            self.assertLogs("pipeline.discord_notify", level="INFO") as logs,
        ):
            self.assertEqual(len(expected_ids), self.discord_notify.notify_free_food_events(rows))
        self.assertEqual(expected_ids, fake_client.requests[1][1])
        self.assertEqual(expected_ids, [row["event_id"] for row in fake_client.upserted])
        self.assertEqual(expected_ids, [call.kwargs["json"]["embeds"][0]["title"] for call in post.call_args_list])
        for event_id in expected_ids:
            self.assertTrue(any(f"event_id={event_id}" in line for line in logs.output))

    def test_event_expiring_during_ledger_lookup_is_not_sent(self) -> None:
        self.clock.now.side_effect = [
            datetime(2026, 9, 8, 19, tzinfo=timezone.utc),
            datetime(2026, 9, 8, 19, 0, 1, tzinfo=timezone.utc),
        ]
        row = {
            "id": "expiring",
            "title": "Lunch",
            "has_free_food": True,
            "starts_at": "2026-09-08T18:00:00Z",
            "ends_at": "2026-09-08T19:00:01Z",
        }
        fake_client = FakeClient(existing=[])
        fake_db = types.SimpleNamespace(client=Mock(return_value=fake_client))
        with (
            patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": "https://discord.test"}),
            patch.dict(sys.modules, {"db": fake_db}),
            patch.object(self.discord_notify.requests, "post", return_value=types.SimpleNamespace(status_code=204)) as post,
        ):
            self.assertEqual(0, self.discord_notify.notify_free_food_events([row]))
        self.assertTrue(fake_client.requests)
        self.assertEqual([], fake_client.upserted)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
