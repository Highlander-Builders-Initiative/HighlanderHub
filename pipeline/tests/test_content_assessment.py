"""Contract/grounding tests; semantic accuracy is measured by the live eval."""
import copy
import json
import sys
import unittest
from datetime import date, datetime
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
        result["occurrences"][0].update(all_day=True, starts_at="2026-09-15T00:00:00-07:00",
                                        ends_at="2026-09-15T23:59:59-07:00")
        with self.assertRaisesRegex(ValueError, "midnight boundaries.*Workshop"):
            assess.validate(result, src)

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
        with patch("google.genai.Client") as client:
            client.return_value.models.generate_content.return_value = response
            assess.assess(src)
        options = types.HttpRetryOptions(**client.call_args.kwargs["http_options"]["retry_options"])
        for code, expected in ((429, 4), (503, 4), (400, 1), (403, 1)):
            operation = Mock(side_effect=errors.APIError(code, {"error": {"message": "test"}}))
            sleeps = []
            retry = tenacity.Retrying(**_api_client.retry_args(options), sleep=sleeps.append)
            with self.subTest(code=code), self.assertRaises(errors.APIError):
                retry(operation)
            self.assertEqual(expected, operation.call_count)
            if sleeps:
                self.assertTrue(5 <= sleeps[0] <= 6)
                self.assertTrue(all(delay <= 30 for delay in sleeps))


if __name__ == "__main__":
    unittest.main()
