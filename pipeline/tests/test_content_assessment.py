"""Contract/grounding tests; semantic accuracy is measured by the live eval."""
import copy
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

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
    def test_valid_activity_retains_timestamps(self):
        src = source()
        self.assertEqual(decision(src), assess.validate(decision(src), src))

    def test_model_quotes_must_exist_in_original_source(self):
        src, result = source(), decision(source())
        result["occurrences"][0]["activity_evidence"] = [{"field":"ocr_text", "quote":"Invented workshop"}]
        with self.assertRaisesRegex(ValueError, "absent"):
            assess.validate(result, src)

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
        for origin in ("instagram", "localist", "highlander_link"):
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
        self.assertEqual("other", classify_content_kind("localist", title="Staff Workshop", audiences=["Staff"], assessed_kind="activity"))
        self.assertEqual("fundraiser", classify_content_kind("instagram", title="Bake sale", assessed_kind="activity"))
        self.assertEqual("student_deadline", classify_content_kind("instagram", title="Submit your essay", assessed_kind="deadline"))


if __name__ == "__main__":
    unittest.main()
