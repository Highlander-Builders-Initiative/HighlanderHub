"""Regressions from the September 28 published content audit, using its saved source text."""
import sys
import unittest
import json
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
import content_assessment as assess
import instagram_rows
from classify import detect_free_food, title_offers_boba

CASES = json.loads((Path(__file__).parent / "fixtures/sep28-sources.json").read_text())
NOW = "2026-09-28T19:27:05+00:00"


def rows(name):
    case = CASES[name]
    record = {**case["post"], "caption": case["source"]["texts"]["caption"]}
    cached = {"status": "ok", "images": [
        {**image, "image_url": f"https://cdn.example/{case['post']['media_id']}_{image['index']}.jpg"}
        for image in case["images"]]}
    source = publication.post_source(record, cached)
    assert source == case["source"], "fixture no longer reproduces the saved source"
    result = assess.validate(assess._attach_source_quotes(case["result"], source), source)
    return {row["title"]: row for row in publication.post_rows(
        record, cached, {"status": "complete", "result": result, "source": source}, {}, NOW)[0]}


class SessionDeadlineTests(unittest.TestCase):
    """An activity post can also print a cutoff; that session is a deadline."""

    def test_the_cleanup_signup_cutoff_is_a_deadline(self):
        published = rows("pds_cleanup")
        self.assertEqual(published["Volunteer Cleanup Event Sign-up Deadline"]["content_kind"], "student_deadline")
        self.assertEqual(published["Volunteer Cleanup Event"]["content_kind"], "student_event")

    def test_the_recruitment_application_cutoff_is_a_deadline(self):
        published = rows("pse_recruitment")
        self.assertEqual(published["Application Deadline"]["content_kind"], "student_deadline")
        for title in ("Info Night", "Guest Speaker Session", "BBQ w/ the Bros"):
            self.assertEqual(published[title]["content_kind"], "student_event")


class FreeFoodTests(unittest.TestCase):
    """A trip to a boba shop, or a sibling session's boba, is not free food."""

    def test_no_session_inherits_a_boba_shop_as_free_food(self):
        audited = {
            "csa_welcome": ("Boba Tea House", "Info Night", "CCN Info Night", "Field Day"),
            "designing_dreams": ("Sewing Kits- First Meeting!", "Tailoring Pop-up", "Beginner Workshop",
                                 "Rave/Halloween Meeting", "Intermediate Workshop"),
            "aacf_welcome": ("Outreach Night", "Freshman Night", "Small Group Kickoff"),
            "pse_recruitment": ("Application Deadline", "Boba Tea House Social"),
        }
        flagged = {name: [title for title in titles if rows(name)[title]["has_free_food"]]
                   for name, titles in audited.items()}
        self.assertEqual(flagged, {name: [] for name in audited})

    def test_msa_tabling_and_cafe_sessions_are_not_free_food(self):
        published = rows("msa_welcome")
        for title in ("Fall Involvement Fair", "Club Mixer", "Qamaria Social"):
            self.assertFalse(published[title]["has_free_food"], title)

    def test_offered_food_still_counts(self):
        self.assertTrue(detect_free_food("Free boba for the first 50 people"))
        self.assertTrue(detect_free_food("Pizza provided!"))
        self.assertFalse(detect_free_food("9/28: Boba tea house (shuttling @ Lot 15)"))
        self.assertTrue(detect_free_food("Design 101\nFree Merch & boba!"))
        self.assertTrue(detect_free_food("a chill 5 mile ride and free 16 oz. Boba for riders only!"))
        # Trivia Night (ig_awwcucr_p3992906422932732771) had to be flagged by hand.
        self.assertTrue(detect_free_food("trivia questions for all majors alike! Food and drinks will be provided"))
        self.assertTrue(detect_free_food("Lunch is provided"))
        self.assertFalse(detect_free_food("Transportation will be provided"))
        self.assertFalse(detect_free_food("Food for purchase"))

    def test_a_session_titled_for_its_boba_still_counts(self):
        for title, offered in (("Games & Boba", True), ("Scavenger Hunt & Boba Social", True),
                               ("Boba Social", True), ("Boba Tea House", False),
                               ("Boba Tea House Social", False), ("KRAK Boba Fundraiser", False)):
            with self.subTest(title=title):
                self.assertIs(title_offers_boba(title), offered)
        published = rows("designing_dreams")
        self.assertTrue(published["Boba Social"]["has_free_food"])


class MeetingLinkTests(unittest.TestCase):
    """A Zoom link to join is kept, but joining a call is not registering."""

    def test_a_zoom_join_link_is_not_an_rsvp_requirement(self):
        meeting = rows("asig_intro")["Anesthesiology Introductory Meeting"]
        self.assertEqual(meeting["rsvp_url"], "https://ucr.zoom.us/j/98095293822")
        self.assertFalse(meeting["rsvp_required"])

    def test_every_cmsp_session_keeps_its_link_without_requiring_rsvp(self):
        published = list(rows("cmsp_sessions").values())
        self.assertTrue(published)
        for row in published:
            self.assertEqual(row["rsvp_url"], "https://ucr.zoom.us/j/94905110745")
            self.assertFalse(row["rsvp_required"])

    def test_a_zoom_webinar_registration_page_is_still_registration(self):
        self.assertIsNone(instagram_rows._MEETING_JOIN_URL.match(
            "https://us02web.zoom.us/webinar/register/WN_XshA9Ds7SUqB6hrLzN3R2A"))


class YearlessDateTests(unittest.TestCase):
    """'WED. MAY 27' posted May 26, 2026 is the next day, not a year later."""

    def test_a_year_after_the_next_occurrence_is_refused(self):
        case = CASES["polisci_awards"]
        with self.assertRaises(ValueError):
            assess.validate(assess._attach_source_quotes(case["result"], case["source"]), case["source"])

    def test_the_next_occurrence_is_accepted(self):
        case = CASES["polisci_awards"]
        result = json.loads(json.dumps(case["result"]))
        result["occurrences"][0]["starts_at"] = "2026-05-27T16:00:00-07:00"
        assess.validate(assess._attach_source_quotes(result, case["source"]), case["source"])

    def test_rollover_and_earlier_opening_days_stay_supported(self):
        for posted, printed, day, supported in (
            ("2026-12-20T20:00:00Z", "Mixer Jan 5", date(2027, 1, 5), True),
            ("2026-12-20T20:00:00Z", "Mixer Jan 5", date(2026, 1, 5), False),
            ("2026-09-20T20:00:00Z", "Apply by May 1", date(2027, 5, 1), True),
            ("2026-09-20T20:00:00Z", "Exhibition opened Sep 1", date(2026, 9, 1), True),
            ("2026-09-20T20:00:00Z", "Garba Night Oct 4", date(2025, 10, 4), False),
        ):
            with self.subTest(posted=posted, day=day):
                self.assertIs(assess._day_supported(day, printed, {"posted_at": posted}), supported)


if __name__ == "__main__":
    unittest.main()
