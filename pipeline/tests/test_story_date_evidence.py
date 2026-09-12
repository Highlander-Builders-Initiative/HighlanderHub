"""Source evidence is required even when Gemini returns a successful event."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extract_stories as extract


class StoryDateEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = {"id": "123", "handle": "club", "posted_at": "2026-09-08T18:00:00Z"}
        self.cached = {
            "status": "ok",
            "result": {
                "is_event": True,
                "title": "Workshop",
                "starts_at": "2026-09-09T12:00:00-07:00",
                "confidence": "high",
            },
        }

    def test_reported_informational_posts_are_rejected_and_old_ids_retired(self) -> None:
        fixtures = json.loads(
            (Path(__file__).parent / "fixtures/undated_story_extractions.json").read_text()
        )
        rows, retired, _ = extract._collect_event_rows(
            [(f["raw"], f["cached"]) for f in fixtures], {}, "2026-09-09T20:00:00Z"
        )
        self.assertEqual([], rows)
        # ucrbusiness reshared a ucrcareercenter post, so both the crawled
        # account's ID and the author-keyed one are retired: either may exist
        # in the table from a run before or after the reshare re-key.
        self.assertEqual({
            "ig_ucrpse_20260908T0700Z",
            "ig_ucrbusiness_20260909T0700Z",
            "ig_ucrcareercenter_20260909T0700Z",
            "ig_ucrbcoe_20260908T0700Z",
        }, retired)

    def test_missing_or_nondating_source_text_cannot_use_model_or_metadata_dates(self) -> None:
        for text in (
            None, "", 123, "Tips for success", "Introducing our Fall '26 board",
            "Summer 2026 Internship Spotlights", "September is awareness month",
            "Open at 12PM", "Room 205/206", "99/99", "September 99", "1-2 PM",
            "Workshop 09/09", "Half off 1/2 price boba", "EKG reading 5.62",
            "Happy Friday from the board", "Monday motivation",
            "Apply now for internships", "Applications are now open",
            "Secretary now accepting applications", "Follow us rn",
            "https://example.com/2026/09/09", "@september9",
        ):
            with self.subTest(text=text):
                cached = {**self.cached, "ocr_text": text, "extracted_at": self.raw["posted_at"]}
                cached["result"] = {**cached["result"], "description": "September 9 workshop",
                                    "tags": ["September 9"]}
                row, _ = extract._to_event_row(
                    {**self.raw, "story_cta_url": "https://example.com/2026/09/09"},
                    cached, {"label": "September 9 Club"}, "2026-09-09T20:00:00Z",
                )
                self.assertIsNone(row)

    def test_explicit_source_dates_do_not_require_a_full_ocr_time_range(self) -> None:
        for text in (
            "Workshop September 9 at noon", "Workshop Sept. 9, 2026",
            "Workshop 9th September 2026", "Workshop 09/09 at 5 PM", "Workshop 9/9/26",
            "Workshop 09.09.2026", "Workshop 2026-09-09",
            "Workshop tomorrow at noon", "Workshop Wednesday at noon",
        ):
            with self.subTest(text=text):
                row, _ = extract._to_event_row(
                    self.raw, {**self.cached, "ocr_text": text}, {}, "2026-09-09T20:00:00Z"
                )
                self.assertIsNotNone(row)

    def test_caption_can_supply_the_source_date(self) -> None:
        row, _ = extract._to_event_row(
            {**self.raw, "caption": "Join our workshop September 9 at noon"},
            {**self.cached, "ocr_text": "Workshop"}, {}, "2026-09-09T20:00:00Z",
        )
        self.assertIsNotNone(row)

    def test_relative_dates_need_posting_context(self) -> None:
        row, _ = extract._to_event_row(
            {**self.raw, "posted_at": None},
            {**self.cached, "ocr_text": "Workshop tomorrow"}, {}, "2026-09-09T20:00:00Z",
        )
        self.assertIsNone(row)

    def test_happening_now_binds_the_start_to_the_posting_instant(self) -> None:
        # Gemini commonly reports posted_at's UTC value as local wall time, so
        # "starting now" must not inherit the model's clock.
        for text in ("WORKSHOP IS STARTING NOW!", "Pull up to ssc112 rn"):
            with self.subTest(text=text):
                row, retired = extract._to_event_row(
                    self.raw,
                    {**self.cached, "ocr_text": text}, {}, "2026-09-09T20:00:00Z",
                )
                self.assertEqual("2026-09-08T18:00:00+00:00", row["starts_at"])
                self.assertEqual({"ig_club_20260909T1900Z"}, retired)

    def test_today_and_tomorrow_bind_the_day_but_keep_the_model_time(self) -> None:
        for text, expected in (
            ("Doors open today", "2026-09-08T19:00:00+00:00"),
            ("Doors open tomorrow", "2026-09-09T19:00:00+00:00"),
        ):
            with self.subTest(text=text):
                row, _ = extract._to_event_row(
                    self.raw,
                    {**self.cached, "ocr_text": text}, {}, "2026-09-09T20:00:00Z",
                )
                self.assertEqual(expected, row["starts_at"])

    def test_immediacy_shift_preserves_the_event_span(self) -> None:
        row, _ = extract._to_event_row(
            self.raw,
            {**self.cached, "ocr_text": "OPEN TODAY", "result": {
                **self.cached["result"], "ends_at": "2026-09-09T16:00:00-07:00",
            }}, {}, "2026-09-09T20:00:00Z",
        )
        self.assertEqual("2026-09-08T19:00:00+00:00", row["starts_at"])
        self.assertEqual("2026-09-08T23:00:00+00:00", row["ends_at"])

    def test_midnight_on_the_posting_day_falls_back_to_the_post_time(self) -> None:
        # Midnight is the model's "time unknown", not a claim about the event.
        row, _ = extract._to_event_row(
            self.raw,
            {**self.cached, "ocr_text": "Run club TODAY", "result": {
                **self.cached["result"], "starts_at": "2026-09-09T00:00:00-07:00",
            }}, {}, "2026-09-09T20:00:00Z",
        )
        self.assertEqual("2026-09-08T18:00:00+00:00", row["starts_at"])

    def test_a_printed_date_outranks_a_passing_immediacy_word(self) -> None:
        row, _ = extract._to_event_row(
            self.raw,
            {**self.cached, "ocr_text": "Workshop September 9 at noon - apply today"},
            {}, "2026-09-09T20:00:00Z",
        )
        self.assertEqual("2026-09-09T19:00:00+00:00", row["starts_at"])

    def test_call_to_action_now_is_not_date_evidence(self) -> None:
        for text in (
            "Apply now for internships", "Register now for the fair",
            "Applications are now open", "Follow us rn", "Donate now",
            "Book your appointment now", "Reserve your spot now", "Join now",
        ):
            with self.subTest(text=text):
                row, _ = extract._to_event_row(
                    self.raw, {**self.cached, "ocr_text": text}, {},
                    "2026-09-09T20:00:00Z",
                )
                self.assertIsNone(row)

    def test_bare_weekday_needs_a_clock_time(self) -> None:
        row, _ = extract._to_event_row(
            self.raw, {**self.cached, "ocr_text": "Happy Friday from the board"},
            {}, "2026-09-09T20:00:00Z",
        )
        self.assertIsNone(row)
        row, _ = extract._to_event_row(
            self.raw, {**self.cached, "ocr_text": "General meeting Friday 6:30 PM"},
            {}, "2026-09-09T20:00:00Z",
        )
        self.assertIsNotNone(row)

    def test_a_slash_date_range_corroborates_itself(self) -> None:
        # "10/8-10/11" is a run of days; fractions do not come in ranges.
        for text, start in (
            ("RECRUITMENT IS 10/8-10/11", "2026-10-08T12:00:00-07:00"),
            ("Limited slots from 9/21 - 10/02", "2026-09-21T12:00:00-07:00"),
            ("Tabling 10/8 to 10/11", "2026-10-08T12:00:00-07:00"),
        ):
            with self.subTest(text=text):
                row, _ = extract._to_event_row(
                    self.raw, {**self.cached, "ocr_text": text, "result": {
                        **self.cached["result"], "starts_at": start,
                    }}, {},
                    "2026-09-09T20:00:00Z",
                )
                self.assertIsNotNone(row)

    def test_a_weekday_beside_a_slash_date_corroborates_it(self) -> None:
        # Neither half is evidence alone, but printed together they name a day.
        row, _ = extract._to_event_row(
            {**self.raw, "posted_at": "2026-06-10T18:00:00Z"},
            {**self.cached, "ocr_text": "Signups close Thursday (6/11)"},
            {}, "2026-09-09T20:00:00Z",
        )
        self.assertIsNotNone(row)
        row, _ = extract._to_event_row(
            self.raw,
            {**self.cached, "ocr_text": "Happy Friday! Half off 1/2 price boba"},
            {}, "2026-09-09T20:00:00Z",
        )
        self.assertIsNone(row)

    def test_a_printed_slash_range_outranks_a_booking_cta(self) -> None:
        # "BOOK ... NOW" is a call to action, so the printed run of days stands
        # instead of collapsing the event onto the story's post time.
        row, _ = extract._to_event_row(
            self.raw,
            {**self.cached, "ocr_text": (
                "Board Member Coffee Chats\nBOOK YOUR APPOINTMENT NOW\n"
                "Limited slots from 9/21 - 10/02"
            ), "result": {**self.cached["result"], "starts_at": "2026-09-21T09:00:00-07:00"}},
            {}, "2026-09-09T20:00:00Z",
        )
        self.assertEqual("2026-09-21T16:00:00+00:00", row["starts_at"])

    def test_happening_now_reminders_keep_their_source_date(self) -> None:
        for text in ("Workshop starting NOW!", "Finals Refuel happening rn till 2pm!"):
            with self.subTest(text=text):
                row, _ = extract._to_event_row(
                    self.raw,
                    {**self.cached, "ocr_text": text, "result": {
                        **self.cached["result"], "starts_at": self.raw["posted_at"],
                    }}, {}, "2026-09-09T20:00:00Z",
                )
                self.assertIsNotNone(row)

    def test_main_routes_cached_source_to_assessment_before_publication(self) -> None:
        with (
            patch.object(extract, "ensure_dirs"),
            patch.object(extract, "_load_account_meta", return_value={"club": {}}),
            patch.object(extract, "_iter_raw_stories", return_value=[self.raw]),
            patch.object(extract, "_process_story", return_value=self.cached),
            patch("assessed_events.publish_stories") as publish,
            patch.object(extract, "_upsert_events") as upsert,
        ):
            extract.main()
        self.assertEqual([(self.raw, self.cached)], publish.call_args.args[0])
        upsert.assert_not_called()

    def test_cleanup_keeps_a_valid_story_sharing_the_rejected_event_id(self) -> None:
        valid = {**self.cached, "ocr_text": "Workshop September 9 at noon"}
        rows, retired, _ = extract._collect_event_rows(
            [(self.raw, self.cached), (self.raw, valid)], {"club": {}}, "2026-09-09T20:00:00Z"
        )
        self.assertEqual(set(), retired - {row["id"] for row in rows})
        self.assertEqual(["ig_club_20260909T1900Z"], [row["id"] for row in rows])


if __name__ == "__main__":
    unittest.main()
