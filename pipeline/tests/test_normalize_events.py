from __future__ import annotations

import importlib
import sys
import types
import unittest
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
        fake_db = types.SimpleNamespace(upsert_batched=Mock())
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
                "localist_url": "javascript:alert(1)",
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


if __name__ == "__main__":
    unittest.main()
