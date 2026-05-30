from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))


class StructuredScraperTests(unittest.TestCase):
    def setUp(self) -> None:
        sys.modules.pop("ucr_events", None)
        sys.modules.pop("highlander_link", None)
        self.ucr_events = importlib.import_module("ucr_events")
        self.highlander_link = importlib.import_module("highlander_link")

    def tearDown(self) -> None:
        sys.modules.pop("ucr_events", None)
        sys.modules.pop("highlander_link", None)

    def test_ucr_events_prunes_raw_files_absent_from_completed_scrape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            (source_dir / "123.json").write_text("{}", encoding="utf-8")
            (source_dir / "456.json").write_text("{}", encoding="utf-8")

            with patch.object(self.ucr_events, "SOURCE_DIR", source_dir):
                removed = self.ucr_events._prune_missing_events({"123"})

            self.assertEqual(1, removed)
            self.assertTrue((source_dir / "123.json").exists())
            self.assertFalse((source_dir / "456.json").exists())

    def test_highlander_link_prunes_raw_files_absent_from_completed_scrape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            (source_dir / "123.json").write_text("{}", encoding="utf-8")
            (source_dir / "456.json").write_text("{}", encoding="utf-8")

            with patch.object(self.highlander_link, "SOURCE_DIR", source_dir):
                removed = self.highlander_link._prune_missing_events({"456"})

            self.assertEqual(1, removed)
            self.assertFalse((source_dir / "123.json").exists())
            self.assertTrue((source_dir / "456.json").exists())


if __name__ == "__main__":
    unittest.main()
