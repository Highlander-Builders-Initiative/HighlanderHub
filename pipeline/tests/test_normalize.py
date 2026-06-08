from __future__ import annotations

import importlib
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))


class NormalizeWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.normalize = importlib.import_module("normalize")

    def test_within_window_keeps_recent_drops_old_keeps_unparseable(self) -> None:
        cutoff = datetime(2026, 6, 1, tzinfo=timezone.utc)
        self.assertTrue(self.normalize._within_window("2026-06-05T00:00:00Z", cutoff))
        self.assertFalse(self.normalize._within_window("2026-05-01T00:00:00Z", cutoff))
        # Never drop on a missing/garbage timestamp — re-upsert instead.
        self.assertTrue(self.normalize._within_window(None, cutoff))
        self.assertTrue(self.normalize._within_window("not-a-date", cutoff))

    def test_main_upserts_only_stories_within_window(self) -> None:
        recent = (
            (datetime.now(timezone.utc) - timedelta(days=1))
            .isoformat()
            .replace("+00:00", "Z")
        )
        items = [
            {"id": "new1", "handle": "acm_ucr", "posted_at": recent},
            {"id": "old1", "handle": "acm_ucr", "posted_at": "2000-01-01T00:00:00Z"},
        ]

        with patch.object(self.normalize, "STORIES_WINDOW_DAYS", 30):
            with patch.object(self.normalize, "ensure_dirs"):
                with patch.object(
                    self.normalize, "_load_account_meta", return_value={"acm_ucr": {}}
                ):
                    with patch.object(self.normalize, "collect", return_value=items):
                        with patch.object(
                            self.normalize, "upsert_batched", return_value=1
                        ) as upsert:
                            self.normalize.main()

        upsert.assert_called_once()
        table, rows = upsert.call_args.args
        self.assertEqual("stories", table)
        self.assertEqual(["new1"], [r["id"] for r in rows])

    def test_window_disabled_upserts_everything(self) -> None:
        items = [
            {"id": "new1", "handle": "acm_ucr", "posted_at": "2026-06-05T00:00:00Z"},
            {"id": "old1", "handle": "acm_ucr", "posted_at": "2000-01-01T00:00:00Z"},
        ]

        with patch.object(self.normalize, "STORIES_WINDOW_DAYS", 0):
            with patch.object(self.normalize, "ensure_dirs"):
                with patch.object(
                    self.normalize, "_load_account_meta", return_value={"acm_ucr": {}}
                ):
                    with patch.object(self.normalize, "collect", return_value=items):
                        with patch.object(
                            self.normalize, "upsert_batched", return_value=2
                        ) as upsert:
                            self.normalize.main()

        _, rows = upsert.call_args.args
        self.assertEqual({"new1", "old1"}, {r["id"] for r in rows})


if __name__ == "__main__":
    unittest.main()
