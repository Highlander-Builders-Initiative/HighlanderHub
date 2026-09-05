from __future__ import annotations

import importlib
import sys
import tempfile
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

    def test_build_host_prefixes_event_type_fallback_with_ucr(self) -> None:
        host = self.normalize_events._build_host(
            {"filters": {"event_types": [{"name": "Recreation"}]}}
        )
        self.assertEqual(host, "UCR Recreation")

    def test_build_host_keeps_real_organizer_unprefixed(self) -> None:
        host = self.normalize_events._build_host(
            {
                "custom_fields": {"department": "Department of Music"},
                "filters": {"event_types": [{"name": "Arts"}]},
            }
        )
        self.assertEqual(host, "Department of Music")

    def test_build_host_defaults_to_uc_riverside(self) -> None:
        self.assertEqual(self.normalize_events._build_host({}), "UC Riverside")

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
            self.normalize_events.main(["ucr_events_"])

        self.fake_db.upsert_batched.assert_called_once()
        self.fake_db.delete_events_missing_from_ids.assert_called_once_with(
            ["ucr_events_"],
            ["ucr_events_52310591390648_9002"],
        )

    def test_normalizer_does_not_reconcile_unverified_sources(self) -> None:
        with patch.object(
            self.normalize_events,
            "_collect_raw",
            side_effect=[[], []],
        ):
            self.normalize_events.main()

        self.fake_db.delete_events_missing_from_ids.assert_not_called()

    def test_verified_source_rejects_malformed_raw_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp)
            (source_dir / "broken.json").write_text("{", encoding="utf-8")

            with self.assertRaises(ValueError):
                list(
                    self.normalize_events._collect_raw(
                        source_dir,
                        require_complete=True,
                    )
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
        # Free food is now its own attribute; category stays the real type.
        self.assertTrue(rows[0]["has_free_food"])
        self.assertNotEqual("free_food", rows[0]["category"])

    def _localist_category(self, **raw) -> str:
        row = self.normalize_events._to_event_row(
            {"id": 1, "first_date": "2026-05-15T19:00:00-07:00", **raw},
            "2026-05-14T12:00:00+00:00",
        )
        assert row is not None
        return row["category"]

    def _hlink_category(self, **raw) -> str:
        row = self.normalize_events._to_event_row_hlink(
            {"id": 1, "startsOn": "2026-05-15T19:00:00+00:00", **raw},
            "2026-05-14T12:00:00+00:00",
        )
        assert row is not None
        return row["category"]

    def _types(self, *names: str) -> dict:
        return {"filters": {"event_types": [{"name": n} for n in names]}}

    def test_localist_source_type_beats_keywords_in_the_blurb(self) -> None:
        # The regression: Recreation listings whose blurbs say "class" used to
        # come back academic, because "academic" was simply first in the
        # keyword list and "class" matched as a substring.
        for title in ("Power Yoga", "Zumba\u00ae", "Classical Pilates"):
            with self.subTest(title=title):
                self.assertEqual(
                    "sports",
                    self._localist_category(
                        title=title,
                        description_text="A drop-in class at the SRC. All fitness classes are free.",
                        **self._types("Recreation"),
                    ),
                )

    def test_localist_source_types_match_whole_labels(self) -> None:
        self.assertEqual(
            "academic",
            self._localist_category(
                title="Undergrads: Fall Fee Payments Due",
                **self._types("Academic Calendar"),
            ),
        )
        # "Academic Calendar" resolves as itself, and loses to the more
        # specific co-tag rather than to list order.
        self.assertEqual(
            "community",
            self._localist_category(
                title="Commencement 2026",
                **self._types("Academic Calendar", "Commencement"),
            ),
        )

    def test_localist_athletics_filter_wins_outright(self) -> None:
        self.assertEqual(
            "sports",
            self._localist_category(
                title="Men's Soccer vs UNLV",
                filters={
                    "event_types": [{"name": "Social"}],
                    "event_athletics": [{"name": "Soccer"}],
                },
            ),
        )

    def test_keyword_fallback_matches_whole_words_only(self) -> None:
        # No source types at all, so the keyword pass decides. "Classical" and
        # "self-defense" must not read as the academic words they contain.
        self.assertEqual(
            "arts",
            self._localist_category(
                title="Classical Guitar Recital",
                description_text="An evening concert in the gallery.",
            ),
        )

    def test_keyword_fallback_scores_instead_of_taking_the_first_match(self) -> None:
        # One stray "research" in the body no longer outranks a title that
        # names a career event three ways.
        self.assertEqual(
            "career",
            self._localist_category(
                title="Internship Resume Workshop",
                description_text="Bring your research interests.",
            ),
        )

    def test_localist_unmapped_types_fall_through_to_keywords(self) -> None:
        # "Workshops" is deliberately unmapped: it hangs off everything, so it
        # only gets to weigh in as a keyword hint.
        self.assertEqual(
            "career",
            self._localist_category(
                title="Level Up: Decision in a Day",
                description_text="Hiring managers walk you through the process.",
                **self._types("Workshops"),
            ),
        )

    def test_localist_falls_back_to_community(self) -> None:
        self.assertEqual(
            "community",
            self._localist_category(title="Storytime in the Gardens", description_text=""),
        )

    def test_hlink_theme_wins_then_category_names(self) -> None:
        self.assertEqual(
            "community",
            self._hlink_category(name="CMC Street Cleanup", theme="CommunityService"),
        )
        # No theme: the free-text categoryNames get their own explicit pass
        # before any keyword guessing.
        self.assertEqual(
            "arts",
            self._hlink_category(
                name="Silent Disglo",
                categoryNames=["Free Food", "Just Show Up!", "Concert"],
            ),
        )


if __name__ == "__main__":
    unittest.main()
