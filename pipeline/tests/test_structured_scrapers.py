from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


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

    def test_ucr_events_rejects_empty_or_malformed_snapshot(self) -> None:
        payloads = [
            {"page": {"total": 0, "size": 100}, "events": []},
            {"page": {"total": 1, "size": 100}, "events": [{}]},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                with (
                    patch.object(self.ucr_events, "_session", return_value=Mock()),
                    patch.object(self.ucr_events, "_fetch_page", return_value=payload),
                ):
                    with self.assertRaises(ValueError):
                        self.ucr_events.fetch_all()

    def _localist_page(self, pages: int, entries: list) -> dict:
        return {"page": {"current": 1, "size": 100, "total": pages}, "events": entries}

    @staticmethod
    def _localist_entry(eid: str, start: str, instance_id: int) -> dict:
        return {
            "event": {
                "id": eid,
                "title": f"Event {eid}",
                "first_date": start[:10],
                "event_instances": [
                    {"event_instance": {"id": instance_id, "start": start}}
                ],
            }
        }

    def test_ucr_events_walks_every_page_reported_by_page_total(self) -> None:
        """`page.total` is Localist's PAGE count, not its event count."""
        pages = {
            1: self._localist_page(3, [self._localist_entry("a", "2026-09-10T10:00:00-07:00", 1)]),
            2: self._localist_page(3, [self._localist_entry("b", "2026-09-11T10:00:00-07:00", 2)]),
            3: self._localist_page(3, [self._localist_entry("c", "2026-09-12T10:00:00-07:00", 3)]),
        }
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            with (
                patch.object(self.ucr_events, "SOURCE_DIR", source_dir),
                patch.object(self.ucr_events, "_session", return_value=Mock()),
                patch.object(self.ucr_events.time, "sleep"),
                patch.object(
                    self.ucr_events, "_fetch_page", side_effect=lambda s, page: pages[page]
                ),
            ):
                total, new = self.ucr_events.fetch_all()

            self.assertEqual((3, 3), (total, new))
            self.assertEqual(
                {"a", "b", "c"}, {p.stem for p in source_dir.glob("*.json")}
            )

    def test_ucr_events_leaves_previous_snapshot_intact_when_a_page_fails(self) -> None:
        """A mid-walk failure must not half-rewrite the raw directory."""
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            stale = source_dir / "old.json"
            stale.write_text('{"id": "old"}', encoding="utf-8")
            fresh = source_dir / "a.json"
            fresh.write_text('{"id": "a", "title": "previous copy"}', encoding="utf-8")

            def fetch(s, page):
                if page == 1:
                    return self._localist_page(
                        2, [self._localist_entry("a", "2026-09-10T10:00:00-07:00", 1)]
                    )
                raise RuntimeError("page 2 exploded")

            with (
                patch.object(self.ucr_events, "SOURCE_DIR", source_dir),
                patch.object(self.ucr_events, "_session", return_value=Mock()),
                patch.object(self.ucr_events.time, "sleep"),
                patch.object(self.ucr_events, "_fetch_page", side_effect=fetch),
            ):
                with self.assertRaises(RuntimeError):
                    self.ucr_events.fetch_all()

            self.assertEqual(
                {"old", "a"}, {p.stem for p in source_dir.glob("*.json")}
            )
            self.assertEqual(
                '{"id": "a", "title": "previous copy"}', fresh.read_text(encoding="utf-8")
            )
            self.assertEqual('{"id": "old"}', stale.read_text(encoding="utf-8"))

    def test_ucr_events_unions_occurrences_of_a_recurring_event(self) -> None:
        """Localist paginates by occurrence; each entry carries only its own."""
        pages = {
            1: self._localist_page(
                2,
                [
                    self._localist_entry("r", "2026-09-10T06:30:00-07:00", 11),
                    self._localist_entry("r", "2026-09-17T06:30:00-07:00", 12),
                ],
            ),
            2: self._localist_page(
                2, [self._localist_entry("r", "2026-09-03T06:30:00-07:00", 10)]
            ),
        }
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            with (
                patch.object(self.ucr_events, "SOURCE_DIR", source_dir),
                patch.object(self.ucr_events, "_session", return_value=Mock()),
                patch.object(self.ucr_events.time, "sleep"),
                patch.object(
                    self.ucr_events, "_fetch_page", side_effect=lambda s, page: pages[page]
                ),
            ):
                total, _ = self.ucr_events.fetch_all()

            self.assertEqual(1, total)
            saved = json.loads((source_dir / "r.json").read_text(encoding="utf-8"))
            starts = [i["event_instance"]["start"] for i in saved["event_instances"]]
            self.assertEqual(
                [
                    "2026-09-03T06:30:00-07:00",
                    "2026-09-10T06:30:00-07:00",
                    "2026-09-17T06:30:00-07:00",
                ],
                starts,
            )

    def test_highlander_link_leaves_previous_snapshot_intact_when_a_page_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            prior = source_dir / "a.json"
            prior.write_text('{"id": "a", "name": "previous copy"}', encoding="utf-8")

            def fetch(s, skip, ends_after):
                if skip == 0:
                    return {
                        "@odata.count": 101,
                        "value": [
                            {"id": f"e{n}", "name": f"E{n}", "startsOn": "2026-09-10T10:00:00Z"}
                            for n in range(100)
                        ],
                    }
                raise RuntimeError("page 2 exploded")

            with (
                patch.object(self.highlander_link, "SOURCE_DIR", source_dir),
                patch.object(self.highlander_link, "_session", return_value=Mock()),
                patch.object(self.highlander_link.time, "sleep"),
                patch.object(self.highlander_link, "_fetch_page", side_effect=fetch),
            ):
                with self.assertRaises(RuntimeError):
                    self.highlander_link.fetch_all()

            self.assertEqual({"a"}, {p.stem for p in source_dir.glob("*.json")})
            self.assertEqual(
                '{"id": "a", "name": "previous copy"}', prior.read_text(encoding="utf-8")
            )

    def test_highlander_link_rejects_empty_or_malformed_snapshot(self) -> None:
        payloads = [
            {"@odata.count": 0, "value": []},
            {"@odata.count": 1, "value": [{}]},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                with (
                    patch.object(self.highlander_link, "_session", return_value=Mock()),
                    patch.object(self.highlander_link, "_fetch_page", return_value=payload),
                ):
                    with self.assertRaises(ValueError):
                        self.highlander_link.fetch_all()


if __name__ == "__main__":
    unittest.main()
