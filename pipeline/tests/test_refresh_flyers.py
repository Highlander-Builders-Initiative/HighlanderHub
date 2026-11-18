import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import refresh_flyers as rf  # noqa: E402

NOW = datetime(2026, 11, 18, tzinfo=timezone.utc)


def cdn(key, sig):
    return f"https://cdn.example/v/t51/{key}.jpg?oh={sig}&oe=1"


def record(media_id, code, keys, sig="old"):
    return {"media_id": media_id, "handle": "club", "shortcode": code,
            "media": [{"index": i, "media_key": key, "image_url": cdn(key, sig)} for i, key in enumerate(keys)]}


class FreshLinkTests(unittest.TestCase):
    def test_carousel_and_single_posts_map_media_keys_to_their_largest_link(self):
        carousel = {"media_type": 8, "carousel_media": [
            {"image_versions2": {"candidates": [{"url": cdn("a", "small"), "width": 10, "height": 10},
                                                {"url": cdn("a", "big"), "width": 99, "height": 99}]}},
            {"image_url": cdn("b", "new")}]}
        self.assertEqual({"a": cdn("a", "big"), "b": cdn("b", "new")}, rf.fresh_links(carousel))
        self.assertEqual({"c": cdn("c", "new")},
                         rf.fresh_links({"media_type": 1, "image_url": cdn("c", "new")}))

    def test_only_matching_slides_change_and_nothing_new_is_none(self):
        saved = record("1", "A", ["a", "b"])
        relinked = rf.relink(saved, {"a": cdn("a", "new"), "z": cdn("z", "new")})
        self.assertEqual([cdn("a", "new"), cdn("b", "old")], [m["image_url"] for m in relinked["media"]])
        self.assertIsNone(rf.relink(saved, {"z": cdn("z", "new")}))
        self.assertIsNone(rf.relink(saved, {"a": cdn("a", "old")}))


class RefreshStageTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.enterContext(patch.object(rf, "RUN_FILE", Path(directory.name) / "run.json"))
        self.enterContext(patch.dict(rf.os.environ, {"REFRESH_MISSING_FLYERS": "true", "APIFY_TOKEN": "t"}))
        self.enterContext(patch.object(rf, "events_without_flyers", return_value={"ev1", "ev2"}))
        self.registry = self.enterContext(patch("assessed_events.load_registry", return_value={
            "instagram:post:1": {"event_ids": ["ev1"]}, "instagram:post:2": {"event_ids": ["ev2"]}}))
        self.enterContext(patch.object(rf, "hydrate_local_posts"))
        self.enterContext(patch.object(rf, "iter_local_posts", return_value=[
            record("1", "A", ["a"]), record("2", "B", ["b"]), record("3", "C", ["c"])]))
        self.write = self.enterContext(patch.object(rf, "write_post"))
        self.mirror = self.enterContext(patch.object(rf, "mirror"))
        self.enterContext(patch.object(rf, "charge_limit_reason", return_value=None))
        self.api = MagicMock()
        self.enterContext(patch.object(rf, "ApifyClient", return_value=self.api))

    def test_off_by_default(self):
        with patch.dict(rf.os.environ, {"REFRESH_MISSING_FLYERS": ""}):
            self.assertEqual({}, rf.main(now=NOW))
        self.api.details.assert_not_called()

    def test_looks_up_only_posts_behind_events_without_flyers_and_saves_fresh_links(self):
        self.api.details.return_value = ({"id": "r", "status": "SUCCEEDED"}, [
            {"kind": "post", "data": {"code": "A", "media_type": 1, "image_url": cdn("a", "new")}},
            {"kind": "post", "data": {"code": "C", "media_type": 1, "image_url": cdn("c", "new")}},
        ])
        stats = rf.main(now=NOW)
        self.registry.assert_called_once_with(event_ids={"ev1", "ev2"})
        self.assertEqual(["A", "B"], self.api.details.call_args.args[0])
        saved = self.write.call_args.args[0]
        self.assertEqual(("1", cdn("a", "new")), (saved["media_id"], saved["media"][0]["image_url"]))
        self.mirror.assert_called_once_with([saved])
        self.assertEqual({"events_without_flyers": 2, "posts": 2, "looked_up": 2, "refreshed": 1,
                          "not_returned": 1, "skipped_over_limit": 0}, stats)
        self.assertTrue(rf.read_json(rf.RUN_FILE.with_name("run-details.json"))["consumed"])

    def test_failed_or_charge_limited_lookups_change_nothing(self):
        self.api.details.return_value = ({"id": "r", "status": "FAILED"}, [])
        with self.assertRaises(RuntimeError):
            rf.main(now=NOW)
        self.api.details.return_value = ({"id": "r", "status": "SUCCEEDED"}, [])
        with patch.object(rf, "charge_limit_reason", return_value="over the ceiling"), \
             self.assertRaises(rf.CollectionDeferred):
            rf.main(now=NOW)
        self.write.assert_not_called()

    def test_spend_is_capped_per_run(self):
        self.api.details.return_value = ({"id": "r", "status": "SUCCEEDED"}, [])
        with patch.object(rf, "MAX_POSTS", 1):
            stats = rf.main(now=NOW)
        self.assertEqual(["A"], self.api.details.call_args.args[0])
        self.assertEqual(1, stats["skipped_over_limit"])


class ActiveEventTests(unittest.TestCase):
    def test_upcoming_or_ongoing_only(self):
        self.assertTrue(rf._active({"starts_at": "2026-11-19T00:00:00Z"}, NOW))
        self.assertTrue(rf._active({"starts_at": "2026-11-01T00:00:00Z", "ends_at": "2026-11-20T00:00:00+00:00"}, NOW))
        self.assertFalse(rf._active({"starts_at": "2026-11-17T00:00:00Z"}, NOW))
        self.assertFalse(rf._active({"starts_at": "bad"}, NOW))


if __name__ == "__main__":
    unittest.main()
