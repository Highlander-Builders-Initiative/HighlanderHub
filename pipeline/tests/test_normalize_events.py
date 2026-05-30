from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))


class NormalizeEventsTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_config = types.SimpleNamespace(
            RAW_DIR=PIPELINE_ROOT / "data" / "raw",
            ensure_dirs=Mock(),
        )
        fake_db = types.SimpleNamespace(
            upsert_batched=Mock(return_value=0),
            delete_events_missing_from_ids=Mock(return_value=0),
            get_deleted_event_ids=Mock(return_value=set()),
        )
        self.fake_db = fake_db
        self.module_patch = patch.dict(
            sys.modules,
            {
                "config": fake_config,
                "db": fake_db,
            },
        )
        self.module_patch.start()
        sys.modules.pop("normalize_events", None)
        self.normalize_events = importlib.import_module("normalize_events")

    def tearDown(self) -> None:
        self.module_patch.stop()
        sys.modules.pop("normalize_events", None)

    def test_localist_mapper_drops_unsafe_optional_urls(self) -> None:
        row = self.normalize_events._to_event_row(
            {
                "id": 123,
                "title": "Security Night Workshop",
                "first_date": "2026-05-15T19:00:00-07:00",
                "localist_url": "link in bio",
                "photo_url": "ftp://cdn.example/flyer.jpg",
                "ticket_url": "mailto:club@example.com",
            },
            "2026-05-14T12:00:00+00:00",
        )

        self.assertIsNotNone(row)
        assert row is not None
        self.assertIsNone(row["source_url"])
        self.assertIsNone(row["image_url"])
        self.assertIsNone(row["rsvp_url"])

    def test_localist_mapper_expands_recurring_event_instances(self) -> None:
        rows = self.normalize_events._to_event_rows(
            {
                "id": 52310591390648,
                "title": "Gardening for Butterflies",
                "recurring": True,
                "description_text": "Docents are available on recurring Sundays.",
                "first_date": "2026-05-17T00:00:00-07:00",
                "last_date": "2026-06-20T17:00:00-07:00",
                "localist_url": "https://events.ucr.edu/event/gardening-for-butterflies",
                "event_instances": [
                    {
                        "event_instance": {
                            "id": 9001,
                            "start": "2026-05-17T09:00:00-07:00",
                            "end": "2026-05-17T12:00:00-07:00",
                        }
                    },
                    {
                        "event_instance": {
                            "id": 9002,
                            "start": "2026-06-07T09:00:00-07:00",
                            "end": "2026-06-07T12:00:00-07:00",
                        }
                    },
                    {
                        "event_instance": {
                            "id": 9003,
                            "start": "2026-06-21T09:00:00-07:00",
                            "end": "2026-06-21T12:00:00-07:00",
                        }
                    },
                ],
            },
            "2026-05-22T15:32:22+00:00",
            now=datetime(2026, 5, 22, 15, 32, tzinfo=timezone.utc),
        )

        self.assertEqual(
            [row["id"] for row in rows],
            [
                "ucr_events_52310591390648_9002",
                "ucr_events_52310591390648_9003",
            ],
        )
        self.assertEqual(rows[0]["starts_at"], "2026-06-07T09:00:00-07:00")
        self.assertEqual(rows[0]["ends_at"], "2026-06-07T12:00:00-07:00")
        self.assertEqual(rows[1]["starts_at"], "2026-06-21T09:00:00-07:00")
        self.assertEqual(rows[1]["ends_at"], "2026-06-21T12:00:00-07:00")
        self.assertNotIn("ucr_events_52310591390648", {row["id"] for row in rows})

    def test_localist_mapper_keeps_single_instance_events_canonical(self) -> None:
        rows = self.normalize_events._to_event_rows(
            {
                "id": 123,
                "title": "Security Night Workshop",
                "first_date": "2026-05-15T19:00:00-07:00",
                "event_instances": [
                    {
                        "event_instance": {
                            "id": 456,
                            "start": "2026-05-15T19:00:00-07:00",
                            "end": "2026-05-15T21:00:00-07:00",
                        }
                    }
                ],
            },
            "2026-05-14T12:00:00+00:00",
            now=datetime(2026, 5, 14, 12, tzinfo=timezone.utc),
        )

        self.assertEqual([row["id"] for row in rows], ["ucr_events_123"])
        self.assertEqual(rows[0]["starts_at"], "2026-05-15T19:00:00-07:00")
        self.assertEqual(rows[0]["ends_at"], "2026-05-15T21:00:00-07:00")

    def test_normalizer_reconciles_structured_import_ids(self) -> None:
        raw = {
            "id": 52310591390648,
            "title": "Gardening for Butterflies",
            "recurring": True,
            "first_date": "2026-05-17T00:00:00-07:00",
            "last_date": "2026-06-20T17:00:00-07:00",
            "event_instances": [
                {
                    "event_instance": {
                        "id": 9002,
                        "start": "2026-06-07T09:00:00-07:00",
                        "end": "2026-06-07T12:00:00-07:00",
                    }
                }
            ],
        }

        with patch.object(
            self.normalize_events,
            "_collect_raw",
            side_effect=[[raw], []],
        ):
            self.normalize_events.main()

        self.fake_db.upsert_batched.assert_called_once()
        self.fake_db.delete_events_missing_from_ids.assert_called_once_with(
            ["ucr_events_", "highlander_link_"],
            ["ucr_events_52310591390648_9002"],
        )

    def test_normalizer_suppresses_admin_deleted_events(self) -> None:
        raw = {
            "id": 123,
            "title": "Security Night Workshop",
            "first_date": "2026-05-15T19:00:00-07:00",
        }
        self.fake_db.get_deleted_event_ids.return_value = {"ucr_events_123"}

        with patch.object(
            self.normalize_events,
            "_collect_raw",
            side_effect=[[raw], []],
        ):
            self.normalize_events.main()

        self.fake_db.upsert_batched.assert_called_once_with("events", [])

    def test_normalizer_suppresses_deleted_duplicate_event_group(self) -> None:
        localist_raw = {
            "id": 123,
            "title": "Life After UCR",
            "first_date": "2026-05-26T14:00:00-07:00",
        }
        hlink_raw = {
            "id": 456,
            "name": "Life After UCR",
            "startsOn": "2026-05-26T21:00:00+00:00",
            "endsOn": "2026-05-26T22:00:00+00:00",
            "benefitNames": ["Free Food"],
        }
        self.fake_db.get_deleted_event_ids.return_value = {"highlander_link_456"}

        with patch.object(
            self.normalize_events,
            "_collect_raw",
            side_effect=[[localist_raw], [hlink_raw]],
        ):
            self.normalize_events.main()

        self.fake_db.upsert_batched.assert_called_once_with("events", [])

    def test_normalizer_dedupes_same_title_and_start_across_sources(self) -> None:
        localist_raw = {
            "id": 123,
            "title": "Life After UCR",
            "description_text": "A planning workshop.",
            "first_date": "2026-05-26T14:00:00-07:00",
        }
        hlink_raw = {
            "id": 456,
            "name": "Life After UCR",
            "description": "<p>A planning workshop.</p>",
            "startsOn": "2026-05-26T21:00:00+00:00",
            "endsOn": "2026-05-26T22:00:00+00:00",
            "benefitNames": ["Free Food"],
        }

        with patch.object(
            self.normalize_events,
            "_collect_raw",
            side_effect=[[localist_raw], [hlink_raw]],
        ):
            self.normalize_events.main()

        rows = self.fake_db.upsert_batched.call_args.args[1]
        self.assertEqual(1, len(rows))
        self.assertEqual("highlander_link_456", rows[0]["id"])
        self.assertEqual("free_food", rows[0]["category"])


if __name__ == "__main__":
    unittest.main()
