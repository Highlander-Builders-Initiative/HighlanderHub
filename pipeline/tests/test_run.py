from __future__ import annotations

import importlib
import sys
import types
import unittest
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

    def tearDown(self) -> None:
        self.module_patch.stop()
        sys.modules.pop("run", None)

    def test_extract_and_normalize_failures_make_pipeline_exit_nonzero_after_all_stages_run(self) -> None:
        calls: list[str] = []

        def succeeds(name: str):
            def inner() -> None:
                calls.append(name)

            return inner

        def fails(name: str):
            def inner() -> None:
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


if __name__ == "__main__":
    unittest.main()
