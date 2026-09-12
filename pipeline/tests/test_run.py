from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

STAGE_ORDER = [
    "ucr_events.scrape",
    "highlander_link.scrape",
    "events.normalize",
    "instagram.scrape",
    "instagram.posts.scrape",
    "instagram.extract",
    "instagram.posts.extract",
    "instagram.publish",
    "instagram.normalize",
    "events.reconcile",
]


class RunMainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stage_names = [
            "extract_stories",
            "extract_posts",
            "highlander_link",
            "normalize",
            "normalize_events",
            "scrape",
            "scrape_posts",
            "ucr_events",
            "reconcile_events",
            "assessed_events",
        ]
        self.fake_modules = {
            name: types.SimpleNamespace(main=Mock(name=f"{name}.main"))
            for name in self.stage_names
        }
        # The Instagram channels are extracted separately and published
        # together, so the runner calls these rather than a module `main`.
        self.fake_modules["extract_stories"]._load_account_meta = Mock(
            name="extract_stories._load_account_meta", return_value={"acm.ucr": {}}
        )
        self.fake_modules["extract_stories"].extract_all = Mock(
            name="extract_stories.extract_all", return_value=[]
        )
        self.fake_modules["extract_posts"].extract_all = Mock(
            name="extract_posts.extract_all", return_value=([], {})
        )
        self.fake_modules["assessed_events"].publish_instagram = Mock(
            name="assessed_events.publish_instagram"
        )
        # Stage name -> the mock the runner actually invokes for it.
        self.stage_mocks = {
            "ucr_events.scrape": self.fake_modules["ucr_events"].main,
            "highlander_link.scrape": self.fake_modules["highlander_link"].main,
            "events.normalize": self.fake_modules["normalize_events"].main,
            "instagram.scrape": self.fake_modules["scrape"].main,
            "instagram.posts.scrape": self.fake_modules["scrape_posts"].main,
            "instagram.extract": self.fake_modules["extract_stories"].extract_all,
            "instagram.posts.extract": self.fake_modules["extract_posts"].extract_all,
            "instagram.publish": self.fake_modules["assessed_events"].publish_instagram,
            "instagram.normalize": self.fake_modules["normalize"].main,
            "events.reconcile": self.fake_modules["reconcile_events"].main,
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
        self.fake_modules["scrape"].main.side_effect = succeeds("instagram.scrape")
        self.fake_modules["ucr_events"].main.side_effect = succeeds("ucr_events.scrape")
        self.fake_modules["highlander_link"].main.side_effect = succeeds(
            "highlander_link.scrape"
        )
        self.stage_mocks["instagram.extract"].side_effect = fails("instagram.extract")
        self.fake_modules["normalize"].main.side_effect = succeeds(
            "instagram.normalize"
        )
        self.fake_modules["normalize_events"].main.side_effect = fails(
            "events.normalize"
        )
        self.fake_modules["reconcile_events"].main.side_effect = succeeds("events.reconcile")

        with self.assertRaises(SystemExit) as raised:
            self.run.main()

        self.assertEqual(1, raised.exception.code)
        self.assertEqual(STAGE_ORDER, calls)
        self.fake_modules["normalize_events"].main.assert_called_once_with(
            ["ucr_events_", "highlander_link_"], notify=False
        )

    def test_failed_structured_scrape_is_not_reconciled(self) -> None:
        self.fake_modules["ucr_events"].main.side_effect = RuntimeError("ucr failed")

        with self.assertRaises(SystemExit):
            self.run.main()

        self.fake_modules["normalize_events"].main.assert_called_once_with(
            ["highlander_link_"], notify=False
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
        self.assertIn(f"1 of {len(STAGE_ORDER)} stages broken: ucr_events.scrape", summary)

        record = self._history()
        self.assertFalse(record["ok"])
        self.assertEqual(STAGE_ORDER, [s["name"] for s in record["stages"]])
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
        self.assertEqual(len(STAGE_ORDER), len(record["stages"]))
        self.fake_modules["extract_stories"].extract_all.assert_called_once()
        self.fake_modules["extract_posts"].extract_all.assert_called_once()
        self.fake_modules["assessed_events"].publish_instagram.assert_called_once()
        self.fake_modules["reconcile_events"].main.assert_called_once()
        self.assertFalse([s for s in record["stages"] if "error" in s])

    def test_history_is_appended_not_overwritten(self) -> None:
        self.run.main()
        self.run.main()
        self.assertEqual(
            2, len(self.history.read_text(encoding="utf-8").strip().splitlines())
        )

    def test_one_failed_extract_still_publishes_the_other_channels_data(self) -> None:
        stories, posts = [({"id": "story"}, {"status": "ok"})], [({"media_id": "post"}, {"status": "ok"})]
        for failed in ("extract_stories", "extract_posts"):
            with self.subTest(failed=failed):
                story_extract = self.fake_modules["extract_stories"].extract_all
                post_extract = self.fake_modules["extract_posts"].extract_all
                story_extract.side_effect = post_extract.side_effect = None
                story_extract.return_value, post_extract.return_value = stories, (posts, {})
                self.fake_modules[failed].extract_all.side_effect = RuntimeError("extract failed")
                with self.assertRaises(SystemExit):
                    self.run.main()
                args = self.fake_modules["assessed_events"].publish_instagram.call_args.args
                self.assertEqual([] if failed == "extract_stories" else stories, args[0])
                self.assertEqual([] if failed == "extract_posts" else posts, args[1])

    def test_empty_account_metadata_is_loaded_only_once(self) -> None:
        loader = self.fake_modules["extract_stories"]._load_account_meta
        loader.return_value = {}
        self.run.main()
        loader.assert_called_once()

    def test_failed_metadata_load_is_retried_by_the_other_channel(self) -> None:
        loader = self.fake_modules["extract_stories"]._load_account_meta
        loader.side_effect = [RuntimeError("account load failed"), {"acm.ucr": {}}]
        posts = [({"media_id": "post"}, {"status": "ok"})]
        self.fake_modules["extract_posts"].extract_all.return_value = (posts, {})
        with self.assertRaises(SystemExit):
            self.run.main()
        args = self.fake_modules["assessed_events"].publish_instagram.call_args.args
        self.assertEqual(([], posts, {"acm.ucr": {}}), args[:3])
        self.assertEqual(2, loader.call_count)

    def test_instagram_scrape_exit_does_not_skip_structured_pipeline(self) -> None:
        self.fake_modules["scrape"].main.side_effect = SystemExit(
            "Instagram credentials required"
        )

        with self.assertRaises(SystemExit) as raised:
            self.run.main()

        self.assertEqual(1, raised.exception.code)
        self.fake_modules["ucr_events"].main.assert_called_once()
        self.fake_modules["highlander_link"].main.assert_called_once()
        self.fake_modules["normalize_events"].main.assert_called_once_with(
            ["ucr_events_", "highlander_link_"], notify=False
        )
        self.fake_modules["extract_stories"].extract_all.assert_called_once()
        self.fake_modules["extract_posts"].extract_all.assert_called_once()
        self.fake_modules["normalize"].main.assert_called_once()

        record = self._history()
        self.assertFalse(record["ok"])
        self.assertEqual(STAGE_ORDER, [s["name"] for s in record["stages"]])
        scrape_stage = next(
            s for s in record["stages"] if s["name"] == "instagram.scrape"
        )
        self.assertEqual(
            "SystemExit: Instagram credentials required", scrape_stage["error"]
        )

    def test_extract_exit_does_not_skip_structured_normalize(self) -> None:
        self.fake_modules["extract_stories"].extract_all.side_effect = SystemExit(
            "Supabase env missing"
        )

        with self.assertRaises(SystemExit) as raised:
            self.run.main()

        self.assertEqual(1, raised.exception.code)
        self.fake_modules["normalize_events"].main.assert_called_once_with(
            ["ucr_events_", "highlander_link_"], notify=False
        )
        record = self._history()
        names = [s["name"] for s in record["stages"]]
        self.assertEqual(STAGE_ORDER, names)
        self.assertLess(
            names.index("events.normalize"), names.index("instagram.extract")
        )
        extract_stage = next(
            s for s in record["stages"] if s["name"] == "instagram.extract"
        )
        self.assertEqual("SystemExit: Supabase env missing", extract_stage["error"])
        self.assertTrue(
            all(s["ok"] for s in record["stages"] if s["name"] != "instagram.extract")
        )

    def test_history_failure_does_not_break_the_run(self) -> None:
        with patch.object(self.run, "RUN_HISTORY", Path("/nope/run_history.jsonl")):
            self.run.main()  # must not raise


if __name__ == "__main__":
    unittest.main()
