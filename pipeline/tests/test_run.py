from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class RunMainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stage_names = [
            "extract_stories",
            "highlander_link",
            "normalize",
            "normalize_events",
            "scrape",
            "ucr_events",
        ]
        self.fake_modules = {
            name: types.SimpleNamespace(main=Mock(name=f"{name}.main"))
            for name in self.stage_names
        }
        self.module_patch = patch.dict(sys.modules, self.fake_modules)
        self.module_patch.start()
        sys.modules.pop("run", None)
        self.run = importlib.import_module("run")

        # Keep run-history writes out of the real pipeline/data directory.
        self.tmp = tempfile.TemporaryDirectory()
        self.history = Path(self.tmp.name) / "run_history.jsonl"
        self.history_patch = patch.object(self.run, "RUN_HISTORY", self.history)
        self.history_patch.start()

    def tearDown(self) -> None:
        self.history_patch.stop()
        self.tmp.cleanup()
        self.module_patch.stop()
        sys.modules.pop("run", None)

    def _history(self) -> dict:
        lines = self.history.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(1, len(lines))
        return json.loads(lines[0])

    def test_extract_and_normalize_failures_make_pipeline_exit_nonzero_after_all_stages_run(self) -> None:
        calls: list[str] = []

        def succeeds(name: str):
            def inner(*_args) -> None:
                calls.append(name)

            return inner

        def fails(name: str):
            def inner(*_args) -> None:
                calls.append(name)
                raise RuntimeError(f"{name} failed")

            return inner

        self.fake_modules["scrape"].main.side_effect = succeeds("instagram.scrape")
        self.fake_modules["ucr_events"].main.side_effect = succeeds("ucr_events.scrape")
        self.fake_modules["highlander_link"].main.side_effect = succeeds(
            "highlander_link.scrape"
        )
        self.fake_modules["extract_stories"].main.side_effect = fails(
            "instagram.extract"
        )
        self.fake_modules["normalize"].main.side_effect = succeeds(
            "instagram.normalize"
        )
        self.fake_modules["normalize_events"].main.side_effect = fails(
            "events.normalize"
        )

        with self.assertRaises(SystemExit) as raised:
            self.run.main()

        self.assertEqual(1, raised.exception.code)
        self.assertEqual(
            [
                "instagram.scrape",
                "ucr_events.scrape",
                "highlander_link.scrape",
                "instagram.extract",
                "instagram.normalize",
                "events.normalize",
            ],
            calls,
        )
        self.fake_modules["normalize_events"].main.assert_called_once_with(
            ["ucr_events_", "highlander_link_"]
        )

    def test_failed_structured_scrape_is_not_reconciled(self) -> None:
        self.fake_modules["ucr_events"].main.side_effect = RuntimeError("ucr failed")

        with self.assertRaises(SystemExit):
            self.run.main()

        self.fake_modules["normalize_events"].main.assert_called_once_with(
            ["highlander_link_"]
        )

    def test_summary_records_every_stage_and_names_the_broken_one(self) -> None:
        self.fake_modules["ucr_events"].main.side_effect = ValueError("page 2 exploded")

        with self.assertRaises(SystemExit):
            with self.assertLogs("pipeline.run", level="INFO") as logged:
                self.run.main()

        summary = "\n".join(logged.output)
        self.assertIn("---- run summary ----", summary)
        self.assertIn("ucr_events.scrape", summary)
        self.assertIn("FAILED", summary)
        self.assertIn("ValueError: page 2 exploded", summary)
        self.assertIn("1 of 6 stages broken: ucr_events.scrape", summary)

        record = self._history()
        self.assertFalse(record["ok"])
        self.assertEqual(
            [
                "instagram.scrape",
                "ucr_events.scrape",
                "highlander_link.scrape",
                "instagram.extract",
                "instagram.normalize",
                "events.normalize",
            ],
            [s["name"] for s in record["stages"]],
        )
        broken = next(s for s in record["stages"] if s["name"] == "ucr_events.scrape")
        self.assertEqual("ValueError: page 2 exploded", broken["error"])
        self.assertTrue(
            all(s["ok"] for s in record["stages"] if s["name"] != "ucr_events.scrape")
        )

    def test_clean_run_records_ok_and_carries_no_error(self) -> None:
        with self.assertLogs("pipeline.run", level="INFO") as logged:
            self.run.main()

        self.assertIn("run ok in", "\n".join(logged.output))
        record = self._history()
        self.assertTrue(record["ok"])
        self.assertEqual(6, len(record["stages"]))
        self.assertFalse([s for s in record["stages"] if "error" in s])

    def test_history_is_appended_not_overwritten(self) -> None:
        self.run.main()
        self.run.main()
        self.assertEqual(
            2, len(self.history.read_text(encoding="utf-8").strip().splitlines())
        )

    def test_summary_still_reported_when_a_stage_exits(self) -> None:
        self.fake_modules["scrape"].main.side_effect = SystemExit(2)

        with self.assertRaises(SystemExit) as raised:
            self.run.main()

        self.assertEqual(2, raised.exception.code)
        record = self._history()
        self.assertFalse(record["ok"])
        self.assertEqual(["instagram.scrape"], [s["name"] for s in record["stages"]])

    def test_history_failure_does_not_break_the_run(self) -> None:
        with patch.object(self.run, "RUN_HISTORY", Path("/nope/run_history.jsonl")):
            self.run.main()  # must not raise


if __name__ == "__main__":
    unittest.main()
