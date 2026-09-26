"""Regressions from the September 26 audit of run #49, using its saved source text."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
import content_assessment as assess
from category_inference import infer_category_from_text
from classify import classify_content_kind
from url_utils import normalize_rsvp_url

CASES = json.loads((Path(__file__).parent / "fixtures/sep26-sources.json").read_text())
NOW = "2026-09-26T19:19:17+00:00"


def post(name):
    case = CASES[name]
    record = {**case["post"], "caption": case["source"]["texts"]["caption"], "media": [
        {"index": image["index"], "is_video": False, "media_key": f"{case['post']['media_id']}_{image['index']}_n",
         "image_url": f"https://cdn.example/{case['post']['media_id']}_{image['index']}.jpg"}
        for image in case["images"]]}
    cached = {"status": "ok", "images": [
        {**image, "media_key": f"{case['post']['media_id']}_{image['index']}_n",
         "image_url": f"https://cdn.example/{case['post']['media_id']}_{image['index']}.jpg"}
        for image in case["images"]]}
    source = publication.post_source(record, cached)
    assert source == case["source"], "fixture no longer reproduces the saved source"
    return record, cached, source


def rows(name, result=None):
    record, cached, source = post(name)
    result = assess.validate(assess._attach_source_quotes(result or CASES[name]["result"], source), source)
    return publication.post_rows(record, cached, {"status": "complete", "result": result, "source": source},
                                 {}, NOW)[0]


class DatedFirstMeetingTests(unittest.TestCase):
    """EMA: weekly Tuesday meetings 'Starting Sept. 29th', with no quarter end."""

    def test_both_saved_responses_stay_refused(self):
        _, _, source = post("ema")
        for response in CASES["ema"]["refused"]:
            with self.assertRaises(ValueError):
                assess.validate(assess._attach_source_quotes(response, source), source)

    def test_refusals_now_point_to_the_dated_first_session(self):
        _, _, source = post("ema")
        for response in CASES["ema"]["refused"]:
            with self.assertRaises(ValueError) as caught:
                assess.validate(assess._attach_source_quotes(response, source), source)
            self.assertIn("first session", str(caught.exception))
        self.assertIn("return that session as the only occurrence", " ".join(assess.PROMPT.split()))

    def test_the_first_meeting_publishes_without_an_invented_quarter_end(self):
        response = copy.deepcopy(CASES["ema"]["refused"][1])
        cited = [{"field": "caption"}, {"field": "slide_1_ocr"}]
        response["occurrences"] = [{
            "title": "EMA Fall Quarter Meeting", "starts_at": "2026-09-29T14:00:00-07:00",
            "ends_at": "2026-09-29T15:00:00-07:00", "all_day": False, "location": "HMNSS 2211",
            "location_evidence": cited, "activity_evidence": cited, "date_evidence": cited}]
        [row] = rows("ema", response)
        self.assertEqual(("2026-09-29T21:00:00+00:00", "HMNSS 2211", "student_event"),
                         (row["starts_at"], row["location"], row["content_kind"]))


class DirectionsQrTests(unittest.TestCase):
    """Riverside Art & Music Festival: the flyer's only QR code opens Google Maps."""

    def test_the_festival_is_arts_with_no_signup(self):
        [row] = rows("festival")
        self.assertEqual(("arts", None, False), (row["category"], row["rsvp_url"], row["rsvp_required"]))

    def test_map_links_are_not_registration(self):
        for url in ("https://maps.app.goo.gl/KpfeSoemNXCk5Wwg8", "https://goo.gl/maps/abc123",
                    "https://www.google.com/maps/place/White+Park", "https://maps.google.com/?q=White+Park",
                    "https://maps.apple.com/?q=White+Park", "https://waze.com/ul?q=White+Park"):
            with self.subTest(url=url):
                self.assertIsNone(normalize_rsvp_url(url))
        for url in ("https://forms.gle/abc123", "https://goo.gl/forms/abc123", "https://www.google.com/forms/x"):
            with self.subTest(url=url):
                self.assertEqual(url, normalize_rsvp_url(url))

    def test_art_and_music_count_in_the_title_not_as_one_attraction(self):
        self.assertEqual("arts", infer_category_from_text("Riverside Art & Music Festival", "workshops, community"))
        self.assertEqual("arts", infer_category_from_text("Art of Arabic Calligraphy Workshop", ""))
        self.assertEqual("community", infer_category_from_text(
            "The Welcome Picnic", "Music, food and games for our community!"))
        self.assertEqual("career", infer_category_from_text("State-of-the-art Resume Workshop", ""))


class LocationGroundingTests(unittest.TestCase):
    """College Night: the saved venue was the model's inference from an audience note."""

    def test_an_inferred_venue_is_refused(self):
        _, _, source = post("college_night")
        result = assess._attach_source_quotes(CASES["college_night"]["result"], source)
        with self.assertRaisesRegex(ValueError, "contains reasoning"):
            assess.validate(result, source)

    def test_an_empty_location_publishes_the_same_event(self):
        result = copy.deepcopy(CASES["college_night"]["result"])
        result["occurrences"][0].update(location="", location_evidence=[])
        [row] = rows("college_night", result)
        self.assertEqual(("", "arts"), (row["location"], row["category"]))

    def test_the_reminder_names_the_venue_but_its_bare_clock_stays_refused(self):
        _, _, source = post("college_night_reminder")
        response = assess._attach_source_quotes(CASES["college_night_reminder"]["refused"][0], source)
        assess._check_location("The Culver Center", assess._plain(source["texts"]["caption"]))
        with self.assertRaisesRegex(ValueError, "clock lacks source support"):
            assess.validate(response, source)

    def test_printed_venues_and_repaired_ocr_still_pass(self):
        for location, cited in (("The Culver Center", "College Night at The Culver Center"),
                                ("Huntington Beach", "HUNTINGT0N BEACH"),
                                ("Location TBD", "Location: likely to be announced soon, TBD")):
            with self.subTest(location=location):
                assess._check_location(location, cited)


class GoodCauseFundraiserTests(unittest.TestCase):
    """Dunk a Dove: 'supporting a good cause' with priced water balloons and buckets."""

    def test_dunk_a_dove_is_not_published(self):
        self.assertEqual([], rows("dunk_a_dove"))

    def test_a_cause_with_priced_participation_is_a_fundraiser(self):
        _, _, source = post("dunk_a_dove")
        self.assertEqual("fundraiser", classify_content_kind(
            "instagram", title="Dunk a Dove", description=source["texts"]["caption"],
            ocr_text=source["texts"]["slide_2_ocr"], assessed_kind="activity"))

    def test_volunteering_for_a_cause_is_still_an_event(self):
        for description, ocr in (("Volunteer with us at the food bank for a good cause!", ""),
                                 ("Join our beach cleanup, all for a good cause.", "Free lunch provided"),
                                 ("Tickets are $5 at the door.", "")):
            with self.subTest(description=description):
                self.assertEqual("student_event", classify_content_kind(
                    "instagram", title="Saturday Outing", description=description, ocr_text=ocr,
                    assessed_kind="activity"))


if __name__ == "__main__":
    unittest.main()
