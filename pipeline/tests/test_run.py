from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import ANY, Mock, patch

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

STAGE_ORDER = [
    "instagram.posts.collect",
    "instagram.posts.extract",
    "instagram.publish",
    "events.reconcile",
]


class RunMainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stage_names = [
            "extract_posts",
            "apify_posts",
            "reconcile_events",
            "assessed_events",
        ]
        self.fake_modules = {
            name: types.SimpleNamespace(main=Mock(name=f"{name}.main"))
            for name in self.stage_names
        }
        self.fake_modules["apify_posts"].PartialCollection = type("PartialCollection", (RuntimeError,), {})
        self.fake_modules["extract_posts"].extract_all = Mock(
            name="extract_posts.extract_all", return_value=([], {})
        )
        self.fake_modules["assessed_events"].publish_posts = Mock(
            name="assessed_events.publish_posts"
        )
        # Stage name -> the mock the runner actually invokes for it.
        self.stage_mocks = {
            "instagram.posts.collect": self.fake_modules["apify_posts"].main,
            "instagram.posts.extract": self.fake_modules["extract_posts"].extract_all,
            "instagram.publish": self.fake_modules["assessed_events"].publish_posts,
            "events.reconcile": self.fake_modules["reconcile_events"].main,
        }
        self.module_patch = patch.dict(sys.modules, self.fake_modules)
        self.module_patch.start()
        sys.modules.pop("run", None)
        self.run = importlib.import_module("run")
        metadata = patch.object(self.run, "load_account_meta", return_value={"acm.ucr": {}})
        metadata.start()
        self.addCleanup(metadata.stop)

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

    def test_extract_failure_make_pipeline_exit_nonzero_after_all_stages_run(self) -> None:
        calls: list[str] = []

        def succeeds(name: str):
            def inner(*_args, **_kwargs) -> None:
                calls.append(name)

            return inner

        def fails(name: str):
            def inner(*_args, **_kwargs) -> None:
                calls.append(name)
                raise RuntimeError(f"{name} failed")

            return inner

        for stage, mock in self.stage_mocks.items():
            mock.side_effect = succeeds(stage)
        self.stage_mocks["instagram.posts.extract"].side_effect = fails("instagram.posts.extract")
        self.fake_modules["reconcile_events"].main.side_effect = succeeds("events.reconcile")

        with self.assertRaises(SystemExit) as raised:
            self.run.main()

        self.assertEqual(1, raised.exception.code)
        self.assertEqual(STAGE_ORDER, calls)


    def test_summary_records_every_stage_and_names_the_broken_one(self) -> None:
        self.fake_modules["apify_posts"].main.side_effect = ValueError("page 2 exploded")

        with self.assertRaises(SystemExit):
            with self.assertLogs("pipeline.run", level="INFO") as logged:
                self.run.main()

        summary = "\n".join(logged.output)
        self.assertIn("---- run summary ----", summary)
        self.assertIn("instagram.posts.collect", summary)
        self.assertIn("FAILED", summary)
        self.assertIn("ValueError: page 2 exploded", summary)
        self.assertIn(f"1 of {len(STAGE_ORDER)} stages broken: instagram.posts.collect", summary)

        record = self._history()
        self.assertFalse(record["ok"])
        self.assertEqual(STAGE_ORDER, [s["name"] for s in record["stages"]])
        broken = next(s for s in record["stages"] if s["name"] == "instagram.posts.collect")
        self.assertEqual("ValueError: page 2 exploded", broken["error"])
        self.assertTrue(
            all(s["ok"] for s in record["stages"] if s["name"] != "instagram.posts.collect")
        )

    def test_clean_run_records_ok_and_carries_no_error(self) -> None:
        with self.assertLogs("pipeline.run", level="INFO") as logged:
            self.run.main()

        self.assertIn("run ok in", "\n".join(logged.output))
        record = self._history()
        self.assertTrue(record["ok"])
        self.assertEqual(len(STAGE_ORDER), len(record["stages"]))
        self.fake_modules["extract_posts"].extract_all.assert_called_once()
        self.fake_modules["assessed_events"].publish_posts.assert_called_once()
        self.fake_modules["reconcile_events"].main.assert_called_once()
        self.assertFalse([s for s in record["stages"] if "error" in s])

    def test_history_is_appended_not_overwritten(self) -> None:
        self.run.main()
        self.run.main()
        self.assertEqual(
            2, len(self.history.read_text(encoding="utf-8").strip().splitlines())
        )

    def test_archive_snapshot_is_shared_with_extraction_and_fresh_next_run(self):
        collect = self.fake_modules["apify_posts"].main
        extract = self.fake_modules["extract_posts"].extract_all
        self.run.main()
        first = collect.call_args.kwargs["archive"]
        self.assertIs(first, extract.call_args.kwargs["archive"])
        collect.side_effect = RuntimeError("collection failed")
        with self.assertRaises(SystemExit):
            self.run.main()
        second = collect.call_args.kwargs["archive"]
        self.assertIsNot(first, second)
        self.assertIs(second, extract.call_args.kwargs["archive"])

    def test_partial_collection_still_extracts_new_posts_in_full(self) -> None:
        scrape = self.fake_modules["apify_posts"]
        scrape.main.side_effect = scrape.PartialCollection("1 failure(s) and continued past them")
        with self.assertRaises(SystemExit):
            self.run.main()
        self.fake_modules["extract_posts"].extract_all.assert_called_once_with({"acm.ucr"}, cached_only=False, archive=ANY)
        self.assertIn("continued past them", self._history()["stages"][0]["error"])

    def test_failed_collection_still_publishes_extracted_archive(self) -> None:
        archived = [({"media_id": "700"}, {"status": "ok"})]
        self.fake_modules["apify_posts"].main.side_effect = RuntimeError("collection paused")
        self.fake_modules["extract_posts"].extract_all.return_value = (archived, {})
        with self.assertRaises(SystemExit):
            self.run.main()
        self.fake_modules["extract_posts"].extract_all.assert_called_once_with({"acm.ucr"}, cached_only=False, archive=ANY)
        published = self.fake_modules["assessed_events"].publish_posts.call_args
        self.assertEqual(archived, published.args[0])
        self.assertEqual({"acm.ucr": {}}, published.kwargs["meta"])
        self.assertFalse(published.kwargs["notify"])
        self.fake_modules["reconcile_events"].main.assert_called_once()


    def test_empty_account_metadata_is_loaded_only_once(self) -> None:
        loader = self.run.load_account_meta
        loader.return_value = {}
        self.run.main()
        loader.assert_called_once()

    def test_extraction_roadblock_publishes_partial_results_and_writes_resume_report(self):
        completed = [({"media_id": "1"}, {"status": "ok"})]
        self.fake_modules["extract_posts"].extract_all.return_value = (
            completed, {"stopped_at": {"handle": "club", "media_id": "2", "detail": "OCR timeout"}})
        with self.assertRaises(SystemExit):
            self.run.main()
        self.assertEqual(completed, self.fake_modules["assessed_events"].publish_posts.call_args.args[0])
        report = json.loads(self.history.with_name("last_run.json").read_text())
        self.assertFalse(report["ok"])
        self.assertIn("OCR timeout", report["stages"][1]["error"])
        self.assertIn("run.py", report["resume"]["command"])

    def test_interruption_is_recorded_as_incomplete_instead_of_success(self):
        self.fake_modules["apify_posts"].main.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run.main()
        report = json.loads(self.history.with_name("last_run.json").read_text())
        self.assertFalse(report["ok"])
        self.assertIn("interrupted", report["stages"][0]["error"])
        self.fake_modules["extract_posts"].extract_all.assert_not_called()

    def test_failed_metadata_load_is_retried_by_publication(self) -> None:
        loader = self.run.load_account_meta
        loader.side_effect = [RuntimeError("account load failed"), {"acm.ucr": {}}]
        posts = [({"media_id": "post"}, {"status": "ok"})]
        self.fake_modules["extract_posts"].extract_all.return_value = (posts, {})
        with self.assertRaises(SystemExit):
            self.run.main()
        args = self.fake_modules["assessed_events"].publish_posts.call_args.args
        self.assertEqual([], args[0])
        self.assertEqual({"acm.ucr": {}}, self.fake_modules["assessed_events"].publish_posts.call_args.kwargs["meta"])
        self.assertEqual(2, loader.call_count)

    def test_instagram_scrape_exit_does_not_skip_publication(self) -> None:
        self.fake_modules["apify_posts"].main.side_effect = SystemExit(
            "Instagram credentials required"
        )

        with self.assertRaises(SystemExit) as raised:
            self.run.main()

        self.assertEqual(1, raised.exception.code)
        self.fake_modules["extract_posts"].extract_all.assert_called_once()

        record = self._history()
        self.assertFalse(record["ok"])
        self.assertEqual(STAGE_ORDER, [s["name"] for s in record["stages"]])
        scrape_stage = next(
            s for s in record["stages"] if s["name"] == "instagram.posts.collect"
        )
        self.assertEqual(
            "SystemExit: Instagram credentials required", scrape_stage["error"]
        )

    def test_extract_exit_does_not_skip_publication(self) -> None:
        self.fake_modules["extract_posts"].extract_all.side_effect = SystemExit(
            "Supabase env missing"
        )

        with self.assertRaises(SystemExit) as raised:
            self.run.main()

        self.assertEqual(1, raised.exception.code)
        record = self._history()
        names = [s["name"] for s in record["stages"]]
        self.assertEqual(STAGE_ORDER, names)
        extract_stage = next(
            s for s in record["stages"] if s["name"] == "instagram.posts.extract"
        )
        self.assertEqual("SystemExit: Supabase env missing", extract_stage["error"])
        self.assertTrue(
            all(s["ok"] for s in record["stages"] if s["name"] != "instagram.posts.extract")
        )

    def test_history_failure_does_not_break_the_run(self) -> None:
        with patch.object(self.run, "RUN_HISTORY", Path("/nope/run_history.jsonl")):
            self.run.main()  # must not raise


if __name__ == "__main__":
    unittest.main()
