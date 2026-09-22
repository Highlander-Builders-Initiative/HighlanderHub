"""Contract/grounding tests; semantic accuracy is measured by the live eval."""
import copy
import json
import sys
import unittest
from datetime import date, datetime, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import content_assessment as assess
from classify import classify_content_kind


def source(text="Workshop September 15, 2026, 3-5 PM"):
    return {"source_key": "instagram:test", "origin": "instagram", "posted_at": "2026-09-10T17:00:00Z",
            "texts": {"ocr_text": text}, "source_occurrences": []}


def decision(src, kind="activity", role="occurrence"):
    evidence = [{"field": "ocr_text", "quote": src["texts"]["ocr_text"]}]
    return {"kind": kind, "date_role": role, "reason": "Source announces a workshop.",
            "activity_evidence": evidence, "date_evidence": evidence,
            "use_source_occurrences": False, "schedule": None,
            "occurrences": [{"title": "Workshop", "starts_at": "2026-09-15T15:00:00-07:00",
                             "ends_at": "2026-09-15T17:00:00-07:00", "all_day": False, "location": "",
                             "activity_evidence": evidence, "date_evidence": evidence}]}


class ContentAssessmentTests(unittest.TestCase):
    def test_abbreviated_meridiem_requires_a_complete_token(self):
        for text, clock in (("tomorrow at 11a", time(11)), ("at 7p", time(19)),
                            ("at 7:30p", time(19, 30)), ("at 11 a.m.", time(11))):
            with self.subTest(text=text):
                self.assertTrue(assess._clock_supported(clock, text))
        for text in ("11amazing prizes", "11apples", "11 attendees"):
            self.assertFalse(assess._clock_supported(time(11), text))
        self.assertFalse(assess._clock_supported(time(7, 30), "at 7:30p"))

    def test_day_of_month_caption_preserves_explicit_year(self):
        text = "Our first practice is going to be the 28th of September!"
        self.assertTrue(assess._day_supported(date(2026, 9, 28), text, source(text)))
        self.assertFalse(assess._day_supported(date(2026, 9, 28), text.rstrip("!") + " 2025", source(text)))
        self.assertFalse(assess._day_supported(date(2026, 9, 29), text, source(text)))

    def test_explicit_weekday_date_range_supports_its_interior_days(self):
        text = "Welcome Week: Mon, Sept 28 – Wed, Sept 30 | 11:00 AM – 1:00 PM"
        self.assertTrue(assess._day_supported(date(2026, 9, 29), text, source(text)))
        for invalid in (text.replace("Mon", "Tue"), text.replace("Sept 30", "Sept 30, 2025"),
                        "Campaign Sept 28 – Sept 30", "Mon, Sept 21 – Wed, Sept 30"):
            with self.subTest(text=invalid):
                self.assertFalse(assess._day_supported(date(2026, 9, 29), invalid, source(invalid)))
        self.assertFalse(assess._day_supported(date(2026, 10, 1), text, source(text)))

    def test_weekday_range_keeps_explicit_year_on_every_day(self):
        from event_dates import weekday_range_dates

        for text in ("Sun, Sept 28 – Tue, Sept 30, 2025",
                     "Sun, Sept 28, 2025 – Tue, Sept 30"):
            with self.subTest(text=text):
                self.assertEqual({(9, n): {2025} for n in (28, 29, 30)},
                                 weekday_range_dates(text, year=2026))
                for number in (28, 29, 30):
                    self.assertTrue(assess._day_supported(date(2025, 9, number), text, source(text)))
                    self.assertFalse(assess._day_supported(date(2026, 9, number), text, source(text)))

    def test_weekday_range_uses_existing_posted_at_window(self):
        text = "Mon, Sept 28 – Wed, Sept 30"
        # Both years have matching weekdays; only 2026 is near the posting date.
        self.assertTrue(assess._day_supported(date(2026, 9, 29), text, source(text)))
        self.assertFalse(assess._day_supported(date(2037, 9, 29), text, source(text)))

    def test_service_occurrences_require_operating_hours(self):
        src = source("Shop open September 15, 2026")
        result = decision(src, "service_schedule")
        result["occurrences"][0].update(all_day=True, starts_at="2026-09-15T00:00:00-07:00",
                                        ends_at="2026-09-16T00:00:00-07:00")
        with self.assertRaisesRegex(ValueError, "explicit operating hours"):
            assess.validate(result, src)

        src = source("Shop open September 15, 2026 at 3 PM")
        result = decision(src, "service_schedule")
        result["occurrences"][0]["ends_at"] = None
        with self.assertRaisesRegex(ValueError, "explicit operating hours"):
            assess.validate(result, src)

        src = source("Shop open September 15, 2026, 3-5 PM")
        result = decision(src, "service_schedule")
        self.assertEqual(result, assess.validate(result, src))

    def test_saved_refusals_distinguish_parser_defects_from_model_errors(self):
        cases = json.loads((Path(__file__).parent / "fixtures/assessment_refusals.json").read_text())
        for media_id in ("3988684512718732494", "3987093638713207499"):
            case = cases[media_id]
            for attempt in case["attempts"]:
                with self.subTest(media_id=media_id):
                    result = assess._attach_source_quotes(attempt["response"], case["source"])
                    self.assertEqual(result, assess.validate(result, case["source"]))

        case = cases["3989114880493230451"]
        result = assess._attach_source_quotes(case["attempts"][0]["response"], case["source"])
        with self.assertRaisesRegex(ValueError, "both caption and slide"):
            assess.validate(result, case["source"])
        # Only the first webinar has an unambiguous association in this OCR.
        # A top-level caption citation cannot repair its occurrence evidence.
        result["occurrences"] = result["occurrences"][:1]
        caption = {"field": "caption", "quote": case["source"]["texts"]["caption"]}
        result["date_evidence"].append(caption)
        with self.assertRaisesRegex(ValueError, "lacks source support"):
            assess.validate(result, case["source"])
        result["occurrences"][0]["date_evidence"].append(caption)
        self.assertEqual(result, assess.validate(result, case["source"]))

        case = cases["3987615353597995139"]
        for attempt, error in zip(case["attempts"], ("end 11:00:00", "offset disagrees")):
            result = assess._attach_source_quotes(attempt["response"], case["source"])
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                assess.validate(result, case["source"])

    def test_compact_dotted_month_dates_keep_token_and_year_boundaries(self):
        for text in ("SEPT.28 at 5pm", "Sept. 28 at 5pm", "September 28 at 5pm"):
            self.assertTrue(assess._day_supported(date(2026, 9, 28), text, source(text)))
        for text in ("SEPT28", "SEPT.280", "SEPT.28x", "SEPT.28, 2025"):
            self.assertFalse(assess._day_supported(date(2026, 9, 28), text, source(text)))

    def test_ordinal_dates_require_bounded_unambiguous_range_and_day_label(self):
        for separator in ("-", "through the ", "to ", "thru "):
            text = f"September 21st {separator}25th, 2026. DAY 2: Rock Climbing"
            self.assertTrue(assess._day_supported(date(2026, 9, 22), text, source(text)))
            self.assertFalse(assess._day_supported(date(2025, 9, 22), text, source(text)))
            self.assertFalse(assess._day_supported(date(2026, 9, 23), text, source(text)))
        for text in ("DAY 2: Rock Climbing", "September 21-25. Rock Climbing",
                     "September 21-25. DAY 0: Rock Climbing",
                     "September 21-25. DAY 7: Rock Climbing",
                     "September 25-21. DAY 2: Rock Climbing",
                     "September 21-25. October 21-25. DAY 2: Rock Climbing"):
            with self.subTest(text=text):
                self.assertFalse(assess._day_supported(date(2026, 9, 22), text, source(text)))

    def test_unrelated_founding_year_does_not_override_event_year(self):
        src = source("Workshop September 15, 3-5 PM. Women's Resource Center, since 1962.")
        self.assertEqual(decision(src), assess.validate(decision(src), src))

    def test_range_year_still_applies_to_both_endpoints(self):
        for text, endpoints in (("September 6-12, 2026", ((9, 6), (9, 12))),
                                ("August 11 to September 17, 2026", ((8, 11), (9, 17)))):
            src = source(text)
            for month, day in endpoints:
                with self.subTest(text=text, day=day):
                    self.assertTrue(assess._day_supported(date(2026, month, day), text, src))
                    self.assertFalse(assess._day_supported(date(2025, month, day), text, src))

    def test_all_day_repair_identifies_boundary_error_before_date_support(self):
        src = source("Workshop September 15, 2026")
        result = decision(src)
        result["occurrences"][0].update(all_day=True, starts_at="2026-09-15T09:00:00-07:00",
                                        ends_at="2026-09-16T00:00:00-07:00")
        with self.assertRaisesRegex(ValueError, "midnight boundaries.*Workshop"):
            assess.validate(result, src)

    def test_all_day_boundaries_written_as_end_of_day_or_left_open_are_repaired(self):
        for text, starts_at, ends_at, expected in (
            # A deadline: all day, no end, sometimes pinned to the last second.
            ("Applications due September 28, 2026", "2026-09-28T23:59:59-07:00", None,
             ("2026-09-28T00:00:00-07:00", "2026-09-29T00:00:00-07:00")),
            ("Applications due September 28, 2026", "2026-09-28T00:00:00-07:00", None,
             ("2026-09-28T00:00:00-07:00", "2026-09-29T00:00:00-07:00")),
            ("Open house October 6-7, 2026", "2026-10-06T00:00:00-07:00", "2026-10-07T23:59:59-07:00",
             ("2026-10-06T00:00:00-07:00", "2026-10-08T00:00:00-07:00")),
            # The day after the last included day can change offset.
            ("Book sale October 31, 2026", "2026-10-31T00:00:00-07:00", "2026-10-31T23:59:59-07:00",
             ("2026-10-31T00:00:00-07:00", "2026-11-01T00:00:00-07:00")),
            ("Book sale November 1, 2026", "2026-11-01T00:00:00-07:00", None,
             ("2026-11-01T00:00:00-07:00", "2026-11-02T00:00:00-08:00")),
        ):
            with self.subTest(text=text, starts_at=starts_at, ends_at=ends_at):
                src = source(text)
                result = decision(src)
                result["occurrences"][0].update(all_day=True, starts_at=starts_at, ends_at=ends_at)
                occurrence = assess.validate(result, src)["occurrences"][0]
                self.assertEqual(expected, (occurrence["starts_at"], occurrence["ends_at"]))

    def test_timezone_repair_identifies_correct_offset_and_occurrence(self):
        src = source("ID Camp November 21, 2026, 9-11 AM")
        result = decision(src)
        result["occurrences"][0].update(title="ID Camp", starts_at="2026-11-21T09:00:00-07:00",
                                        ends_at="2026-11-21T11:00:00-07:00")
        with self.assertRaisesRegex(ValueError, "2026-11-21T09:00:00-08:00.*ID Camp"):
            assess.validate(result, src)

    def test_caption_all_day_numeric_date_without_clock_is_supported(self):
        src = source("P.s. we loved the Huntington trip so much we are gonna do it again on 9/25 👀✍️")
        result = decision(src)
        result["occurrences"][0].update(all_day=True, starts_at="2026-09-25T00:00:00-07:00",
                                        ends_at="2026-09-26T00:00:00-07:00")
        self.assertEqual(result, assess.validate(result, src))

    def test_valid_activity_retains_timestamps(self):
        src = source()
        self.assertEqual(decision(src), assess.validate(decision(src), src))

    def test_model_quotes_must_exist_in_original_source(self):
        src, result = source(), decision(source())
        result["occurrences"][0]["activity_evidence"] = [{"field":"ocr_text", "quote":"Invented workshop"}]
        with self.assertRaisesRegex(ValueError, "absent"):
            assess.validate(result, src)

    def test_quotes_match_however_the_model_encodes_characters(self):
        for text, quote in (
            ("Nuevo León", "Nuevo Le&oacute;n"),
            ("Nuevo León", "Nuevo Le&#243;n"),
            ("Nuevo León", "Nuevo Le&#xF3;n"),
            ("Nuevo León", "Nuevo Le&amp;oacute;n"),
            ("Nuevo León", "Nuevo Le\\u00f3n"),
            ("Nuevo León", "Nuevo León"),
            ("𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐁𝐚𝐜𝐤", "Welcome Back"),
            ("Wel​come Back", "Welcome Back"),
            ("Practice Info:\nMonday", "Practice Info:\\nMonday"),
            ("Mayor Ishii’s program", "Mayor Ishii's program"),
            ('my Debut Film “Common Sense” will be screened',
             'my Debut Film "Common Sense" will be screened'),
            ("6:00 PM – 8:30 PM", "6:00 PM - 8:30 PM"),
            ("Admission €5", "Admission &euro;5"),
            ("Ages 21+", "Ages 21\\u002b"),
            ("Join 🎉 us at HUB", "Join \\ud83c\\udf89 us at HUB"),
        ):
            with self.subTest(quote=quote):
                src = source(text)
                self.assertTrue(assess.evidence_text([{"field": "ocr_text", "quote": quote}], src))

    def test_character_leniency_does_not_admit_different_words_or_numbers(self):
        for text, quote in (("Sept. 22", "Sept. 23"), ("Sept. 22", "Sept 22"),
                            ("Nuevo León", "Nuevo Leon"), ("Join us 🎉", "🎉"), ("Workshop", "Invented")):
            with self.subTest(quote=quote), self.assertRaisesRegex(ValueError, "absent"):
                assess.evidence_text([{"field": "ocr_text", "quote": quote}], source(text))

    def test_grounding_preserves_meaningful_symbols_and_complete_tokens(self):
        for text, quote in (
            ("Admission $5", "Admission €5"),
            ("Admission $5", "Admission 5"),
            ("Admission $5", "5"),
            ("Ages 21+", "Ages 21"),
            ("Ages 21+ only", "Ages 21 only"),
            ("Discount 50%", "Discount 50"),
            ("Ages ≥21", "Ages 21"),
            ("Ages ≥21", "Ages ≤21"),
            ("September 15-17", "September 15 17"),
            ("September 15-17", "September 15"),
            ("September 15", "September 1"),
            ("NotWorkshop", "Workshop"),
            ("my Debut Film “Common Sense” will be screened",
             "my Debut Film —Common Sense— will be screened"),
            ("⚫ 1:30 pm - 3:00 pm", "• 1:30 pm - 3:00 pm"),
            ("🗓 When: Every Tuesday", "🕰️ When: Every Tuesday"),
            ("Join 🎉us at HUB", "Join us at HUB"),
        ):
            with self.subTest(text=text, quote=quote), self.assertRaisesRegex(ValueError, "absent"):
                assess.evidence_text([{"field": "ocr_text", "quote": quote}], source(text))

    def test_grounding_accepts_intact_substrings_and_later_valid_matches(self):
        for text, quote in (
            ("Details: Admission $5. Register today!", "Admission $5"),
            ("(Ages 21+), bring ID.", "Ages 21+"),
            ("Workshop September 15, 2026.", "September 15"),
            ("Ages 21+ at first; Ages 21 at second.", "Ages 21"),
            ("NotWorkshop. Workshop!", "Workshop"),
        ):
            with self.subTest(text=text, quote=quote):
                self.assertEqual(quote, assess.evidence_text(
                    [{"field": "ocr_text", "quote": quote}], source(text)))

    def test_date_and_time_checks_read_the_decoded_quote(self):
        src = source("Workshop September 15, 2026, 3–5 PM")
        result = decision(src)
        encoded = [{"field": "ocr_text", "quote": "Workshop September 15, 2026, 3&ndash;5 PM"}]
        result["date_evidence"] = result["occurrences"][0]["date_evidence"] = encoded
        self.assertEqual(result, assess.validate(result, src))

    def test_location_citations_are_grounded_and_required_for_named_locations(self):
        src = source("Workshop September 15, 2026, 3-5 PM in HUB 302")
        result = decision(src)
        occurrence = result["occurrences"][0]
        occurrence["location"] = "HUB 302"
        for citations in (None, [], [{"field": "ocr_text", "quote": "Invented room"}],
                          [{"field": "missing_slide", "quote": "HUB 302"}]):
            with self.subTest(citations=citations), self.assertRaises(ValueError):
                occurrence["location_evidence"] = citations
                assess.validate(result, src)
        occurrence["location_evidence"] = [{"field": "ocr_text", "quote": "HUB 302"}]
        self.assertEqual(result, assess.validate(result, src))

    def test_caption_midnight_repair_precedes_duration_validation(self):
        src = source()
        src["texts"] = {"caption": "Workshop September 15, 2026, 9pm–12am"}
        result = decision(source())
        citations = [{"field": "caption", "quote": src["texts"]["caption"]}]
        result.update(activity_evidence=citations, date_evidence=citations)
        result["occurrences"][0].update(
            starts_at="2026-09-15T21:00:00-07:00", ends_at="2026-09-15T00:00:00-07:00",
            activity_evidence=citations, date_evidence=citations)
        validated = assess.validate(result, src)
        self.assertEqual("2026-09-16T00:00:00-07:00", validated["occurrences"][0]["ends_at"])

    def test_midnight_end_requires_source_support_for_the_end_clock(self):
        src = source("Workshop September 15, 2026, starts at 9pm")
        result = decision(src)
        result["occurrences"][0].update(starts_at="2026-09-15T21:00:00-07:00",
                                        ends_at="2026-09-15T00:00:00-07:00")
        before = copy.deepcopy(result)
        with self.assertRaisesRegex(ValueError, "clock lacks source support"):
            assess.validate(result, src)
        self.assertEqual(before, result)

    def test_midnight_normalization_does_not_fix_other_reversed_ranges(self):
        src = source("Workshop September 15, 2026, starts 9pm, ends 8pm")
        result = decision(src)
        result["occurrences"][0].update(starts_at="2026-09-15T21:00:00-07:00",
                                        ends_at="2026-09-15T20:00:00-07:00")
        with self.assertRaisesRegex(ValueError, "duration"):
            assess.validate(result, src)

    def test_midnight_normalization_is_source_independent_and_uses_cited_clocks(self):
        for origin in ("instagram", "campus_website", "manual"):
            for wording in ("9pm–12am", "starts at 9 PM and ends at midnight"):
                with self.subTest(origin=origin, wording=wording):
                    src = source(f"Workshop September 15, 2026, {wording}")
                    src.update(origin=origin, source_key=f"{origin}:test")
                    result = decision(src)
                    result["occurrences"][0].update(starts_at="2026-09-15T21:00:00-07:00",
                                                    ends_at="2026-09-15T00:00:00-07:00")
                    validated = assess.validate(result, src)
                    self.assertEqual("2026-09-16T00:00:00-07:00", validated["occurrences"][0]["ends_at"])

    def test_dates_and_metadata_cannot_establish_activity(self):
        src = source()
        src["texts"]["dates"] = "2026-09-15"
        for field in ("dates", "posted_at", "origin"):
            result = decision(src)
            result["activity_evidence"] = [{"field":field, "quote":src.get(field, "2026-09-15")}]
            with self.assertRaises(ValueError):
                assess.validate(result, src)

    def test_announcement_cannot_smuggle_in_public_occurrences(self):
        src = source()
        for kind, role in (("announcement", "observance"), ("application", "application_window"), ("uncertain", "uncertain")):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "publication choices"):
                assess.validate(decision(src, kind, role), src)

    def test_program_duration_is_nonpublic_and_cannot_be_an_activity_date(self):
        src = source("Summer Scholars Academy: a 7-week program, July 27-September 12, 2026. Earn course credits.")
        result = decision(src, "application", "program_duration")
        result.update(occurrences=[], date_evidence=[{"field": "ocr_text", "quote": src["texts"]["ocr_text"]}])
        self.assertEqual(result, assess.validate(result, src))
        for kind in ("activity", "deadline", "service_schedule"):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "date role disagree"):
                assess.validate({**result, "kind": kind}, src)
        with self.assertRaisesRegex(ValueError, "publication choices"):
            assess.validate({**result, "occurrences": decision(src)["occurrences"]}, src)
        src["source_occurrences"] = [{"starts_at": "2026-07-27T00:00:00-07:00"}]
        with self.assertRaisesRegex(ValueError, "publication choices"):
            assess.validate({**result, "use_source_occurrences": True}, src)

    def test_application_dates_require_evidence_but_undated_programs_are_valid(self):
        src = source("Summer Scholars Academy. Incoming students earn course credits with financial aid available.")
        result = {**decision(src, "application", "none"), "date_evidence": [], "occurrences": []}
        self.assertEqual(result, assess.validate(result, src))
        for role in ("program_duration", "application_window"):
            with self.subTest(role=role), self.assertRaisesRegex(ValueError, "Missing source evidence"):
                assess.validate({**result, "date_role": role}, src)

    def test_unsupported_day_year_clock_and_end_fail(self):
        src = source()
        for key, value in (("starts_at", "2026-09-16T15:00:00-07:00"),
                           ("starts_at", "2027-09-15T15:00:00-07:00"),
                           ("starts_at", "2026-09-15T15:17:00-07:00"),
                           ("starts_at", "2026-09-15T03:00:00-07:00"),
                           ("ends_at", "2026-10-01T17:00:00-07:00"),
                           ("starts_at", "2026-09-15T15:00:00")):
            result = decision(src)
            result["occurrences"][0][key] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                assess.validate(result, src)

    def test_all_day_and_multi_day_activities_do_not_require_clock(self):
        for text, start, end in (
            ("Celebration September 20, 2026", "2026-09-20", "2026-09-21"),
            ("Conference September 18-20, 2026", "2026-09-18", "2026-09-21"),
        ):
            src = source(text)
            result = decision(src)
            result["occurrences"][0].update(starts_at=start+"T00:00:00-07:00", ends_at=end+"T00:00:00-07:00", all_day=True)
            self.assertEqual(result, assess.validate(result, src))

    def test_seasonal_hours_cannot_publish_as_one_timed_span(self):
        # Every endpoint and clock below is printed, so evidence grounding
        # alone accepts the blob; only the duration rule rejects it.
        src = source("Drop-in advising. August 11 to September 17, 2026. Tuesday-Thursday, 10:00 AM to 3:00 PM.")
        for kind in ("activity", "service_schedule"):
            result = decision(src, kind)
            result["occurrences"][0].update(starts_at="2026-08-11T10:00:00-07:00",
                                            ends_at="2026-09-17T15:00:00-07:00")
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "cannot exceed 24 hours"):
                assess.validate(result, src)

    def test_exhibition_visiting_hours_cannot_publish_as_one_timed_span(self):
        src = source("Student Art Exhibition September 1-30, 2026. Visit the gallery daily 10 AM-5 PM.")
        result = decision(src)
        result["occurrences"][0].update(starts_at="2026-09-01T10:00:00-07:00",
                                        ends_at="2026-09-30T17:00:00-07:00")
        with self.assertRaisesRegex(ValueError, "cannot exceed 24 hours"):
            assess.validate(result, src)

    def test_overnight_session_keeps_its_unprinted_next_day_end(self):
        src = source("Late night study jam September 15, 2026, 10 PM-2 AM")
        result = decision(src)
        result["occurrences"][0].update(starts_at="2026-09-15T22:00:00-07:00",
                                        ends_at="2026-09-16T02:00:00-07:00")
        self.assertEqual(result, assess.validate(result, src))

    def test_recurring_hours_cannot_be_standalone_occurrences(self):
        src = source("Drop-in advising August 11 to September 17, 2026. Tuesday-Thursday, 10:00 AM to 3:00 PM.")
        result = decision(src, "service_schedule", "recurring_hours")
        result["occurrences"][0].update(starts_at="2026-08-11T10:00:00-07:00",
                                        ends_at="2026-08-11T15:00:00-07:00")
        with self.assertRaisesRegex(ValueError, "bounded schedule"):
            assess.validate(result, src)
        # Establishing no pattern at all still publishes nothing, rather than
        # failing the assessment and retaining the previous listings.
        result.update(occurrences=[])
        self.assertEqual(result, assess.validate(result, src))

    def test_relative_day_requires_explicit_source_evidence(self):
        src = source("Workshop tomorrow 3-5 PM")
        result = decision(src)
        result["occurrences"][0].update(starts_at="2026-09-11T15:00:00-07:00", ends_at="2026-09-11T17:00:00-07:00")
        assess.validate(result, src)
        result["occurrences"][0]["starts_at"] = "2026-09-10T15:00:00-07:00"
        with self.assertRaises(ValueError):
            assess.validate(result, src)

    def test_recurring_hours_expand_into_weekday_sessions_with_lunch_break(self):
        src = source("Drop-in advising on Zoom August 11 to September 17, 2026. Tuesday-Thursday, 10:00 AM to 3:00 PM, closed for lunch 12-1:00 PM.")
        result = decision(src, "service_schedule", "recurring_hours")
        result.update(occurrences=[], schedule={"first_day":"2026-08-11", "last_day":"2026-09-17", "weekdays":[1,2,3],
                      "windows":[{"start":"10:00", "end":"12:00"},{"start":"13:00", "end":"15:00"}], "title":"Advising", "location":"Zoom",
                      "location_evidence": [{"field": "ocr_text", "quote": "Zoom"}]})
        assess.validate(result, src)
        rows = assess.expand_schedule(result["schedule"], src, result)
        self.assertEqual(36, len(rows))
        for row in rows:
            a, b = map(datetime.fromisoformat, (row["starts_at"], row["ends_at"]))
            self.assertIn(a.weekday(), (1,2,3))
            self.assertEqual(2*3600, (b-a).total_seconds())
            self.assertEqual(result["schedule"]["location_evidence"], row["location_evidence"])
        valid = result["schedule"].pop("location_evidence")
        with self.assertRaisesRegex(ValueError, "Missing source evidence"):
            assess.validate(result, src)
        result["schedule"]["location_evidence"] = valid
        result["schedule"]["weekdays"] = [1,3]
        with self.assertRaisesRegex(ValueError, "weekdays differ"):
            assess.validate(result, src)

    def test_schedule_expansion_shares_the_explicit_occurrence_budget(self):
        for last, expected in (("2026-10-20", 100), ("2026-10-21", None)):
            src = source(f"Gallery visits September 1 to October {last[-2:]}, 2026. Daily 10 AM-12 PM and 1 PM-3 PM.")
            result = decision(src, "service_schedule", "recurring_hours")
            result.update(occurrences=[], schedule={
                "first_day": "2026-09-01", "last_day": last, "weekdays": list(range(7)),
                "windows": [{"start": "10:00", "end": "12:00"}, {"start": "13:00", "end": "15:00"}],
                "title": "Gallery visits", "location": "Gallery",
                "location_evidence": [{"field": "ocr_text", "quote": "Gallery"}]})
            with self.subTest(last=last):
                if expected is None:
                    with self.assertRaisesRegex(ValueError, "exceeds 100"):
                        assess.validate(result, src)
                    with self.assertRaisesRegex(ValueError, "exceeds 100"):
                        assess.expand_schedule(result["schedule"], src, result)
                else:
                    assess.validate(result, src)
                    self.assertEqual(expected, len(assess.expand_schedule(result["schedule"], src, result)))

    def test_semantic_kind_is_independent_of_audience_and_fundraising(self):
        self.assertEqual("other", classify_content_kind("instagram", title="National Service Dog Month", assessed_kind="announcement"))
        self.assertEqual("student_event", classify_content_kind("instagram", title="Awareness Week", assessed_kind="activity"))
        self.assertEqual("other", classify_content_kind("campus_website", title="Staff Workshop", audiences=["Staff"], assessed_kind="activity"))
        self.assertEqual("fundraiser", classify_content_kind("instagram", title="Bake sale", assessed_kind="activity"))
        self.assertEqual("student_deadline", classify_content_kind("instagram", title="Submit your essay", assessed_kind="deadline"))


class AssessmentRequestTests(unittest.TestCase):
    def setUp(self):
        # Requests go to Vertex unless a test opts in; a real key in .env must not leak in.
        patcher = patch("config.GEMINI_API_KEY", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def field_decision(self, src):
        result = decision(src)
        for container in [result, *result["occurrences"]]:
            for key in ("activity_evidence", "date_evidence"):
                container[key] = [{"field": "ocr_text"}]
        return result

    def test_field_references_attach_original_unicode_without_mutating_response(self):
        src = source('Workshop September 15, 2026, 3-5 PM. “Nuevo León!” 🗓️\n• Welcome')
        parsed = self.field_decision(src)
        before = copy.deepcopy(parsed)
        response = SimpleNamespace(parsed=parsed, text=json.dumps(parsed))
        with patch("google.genai.Client") as client:
            client.return_value.models.generate_content.return_value = response
            result = assess.assess(src)
        self.assertEqual(decision(src), result)
        self.assertEqual(before, parsed)

    def test_invalid_fields_and_json_save_both_rejected_responses(self):
        src = source()
        invalid = self.field_decision(src)
        invalid["activity_evidence"] = [{"field": "made_up"}]
        responses = [SimpleNamespace(parsed=invalid, text=json.dumps(invalid)),
                     SimpleNamespace(parsed=None, text="{bad json")]
        with patch("google.genai.Client") as client:
            client.return_value.models.generate_content.side_effect = responses
            with self.assertRaises(assess.GroundingRejected) as raised:
                assess.assess(src)
        self.assertEqual(2, len(raised.exception.attempts))
        self.assertEqual(invalid, raised.exception.attempts[0]["response"])
        self.assertEqual("{bad json", raised.exception.attempts[1]["response"])
        self.assertIn("made_up", raised.exception.attempts[0]["error"])

    def test_explicit_fabricated_quotes_still_fail(self):
        src = source()
        result = decision(src)
        result["activity_evidence"] = [{"field": "ocr_text", "quote": "Fabricated"}]
        with self.assertRaisesRegex(ValueError, "absent"):
            assess.validate(assess._attach_source_quotes(result, src), src)

    def test_configured_transport_retries_are_bounded_and_do_not_retry_bad_requests(self):
        from google.genai import errors, types, _api_client
        import tenacity

        src = source()
        response = SimpleNamespace(parsed=decision(src), text="")
        # A Vertex 429 is transient shared capacity; a free-tier 429 is a spent quota.
        for key, quota_calls in (("", 4), ("test-key", 1)):
            with patch("config.GEMINI_API_KEY", key), patch.object(assess, "FLEX", False), \
                    patch.object(assess, "_pace"), patch("google.genai.Client") as client:
                client.return_value.models.generate_content.return_value = response
                assess.assess(src)
            options = types.HttpRetryOptions(**client.call_args.kwargs["http_options"]["retry_options"])
            self.assertEqual(60_000, client.call_args.kwargs["http_options"]["timeout"])
            for code, expected in ((429, quota_calls), (500, 4), (503, 4), (400, 1), (403, 1)):
                operation = Mock(side_effect=errors.APIError(code, {"error": {"message": "test"}}))
                sleeps = []
                retry = tenacity.Retrying(**_api_client.retry_args(options), sleep=sleeps.append)
                with self.subTest(vertex=not key, code=code), self.assertRaises(errors.APIError):
                    retry(operation)
                self.assertEqual(expected, operation.call_count)
                if sleeps:
                    self.assertTrue(5 <= sleeps[0] <= 6)
                    self.assertTrue(all(delay <= 30 for delay in sleeps))

    def test_free_tier_uses_the_api_key_and_spaces_requests(self):
        src = source()
        response = SimpleNamespace(parsed=decision(src), text="")
        with patch("config.GEMINI_API_KEY", "test-key"), patch.object(assess, "FLEX", False), \
                patch.object(assess, "_last_request", None), \
                patch.object(assess, "monotonic", side_effect=[100.0, 101.0, 104.0]), \
                patch.object(assess, "sleep") as sleep, patch("google.genai.Client") as client:
            client.return_value.models.generate_content.return_value = response
            assess.assess(src)
            assess.assess(src)
        self.assertEqual("test-key", client.call_args.kwargs["api_key"])
        self.assertNotIn("vertexai", client.call_args.kwargs)
        sleep.assert_called_once_with(60 / assess.FREE_TIER_RPM - 1)

    def test_a_spent_daily_quota_stops_without_switching_to_vertex(self):
        from google.genai import errors
        with patch("config.GEMINI_API_KEY", "test-key"), patch.object(assess, "FLEX", False), \
             patch.object(assess, "_pace"), patch("google.genai.Client") as client:
            client.return_value.models.generate_content.side_effect = errors.APIError(
                429, {"error": {"message": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}})
            with self.assertRaises(errors.APIError):
                assess.assess(source())
        client.assert_called_once()
        self.assertEqual("test-key", client.call_args.kwargs["api_key"])
        client.return_value.models.generate_content.assert_called_once()

    def test_flex_is_refused_on_the_gemini_api(self):
        with patch("config.GEMINI_API_KEY", "test-key"), patch.object(assess, "FLEX", True), \
                patch("google.genai.Client") as client:
            with self.assertRaisesRegex(ValueError, "Vertex"):
                assess.assess(source())
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
