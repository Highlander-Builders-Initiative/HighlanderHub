"""Regressions from the September 23 audit of three scheduled runs, using their saved source text."""
import copy
import itertools
import json
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
import content_assessment as assess
from category_inference import infer_category_from_text
from classify import classify_content_kind
from instagram_rows import _requires_signup
from reconcile_events import plan, same_event
from test_post_events import evidence, record

ROWS = {row['id']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/sep23-duplicates.json').read_text())}
NOW = "2026-09-23T19:47:14+00:00"

REACH = ("Applications are OPEN!\n\nWe are now accepting applications for our Fundraising Chair and "
         "Advertising Chair positions. Scan the QR code if you’re interested in applying and joining the "
         "Reach Initiative board!\n\n🗓️ Applications are due October 1st at 11:59 PM!")
RCARD = ("🚨 LAST CHANCE, HIGHLANDERS 🚨\n\nNeed your R’Card to get your wristband for the Block Party? "
         "Make sure you pick it up by 4 PM this Friday!\n\n⚠️ We’re CLOSED on weekends, so Friday is your "
         "last chance! We recommend coming by 3:45 PM at the latest since we close at 4 PM.")
NORTH_DISTRICT = ("TOMORROW NIGHT, the competition is heating up! Jump into this new school year with us at "
                  "our Love Island North District Field Day, located in the B Courtyard from 5 PM - 7:30 PM.")
FAIR = ("Meet hundreds of student organizations on Wednesday September 30th at the Fall Involvement Fair. "
        "It's Fall's largest tabling event and our student leaders want to meet you! See what UCR has to "
        "offer and get involved! No registration required just show up!")


def caption_post(caption, *, media_id, posted_at, handle="club.ucr", ocr=""):
    item = {**record(caption=caption, slides=1, media_id=media_id),
            "handle": handle, "owner_username": handle, "posted_at": posted_at}
    cached = {"status": "ok", "images": [{"media_key": f"{media_id}_0_n", "index": 0,
                                          "ocr_text": ocr, "qr_urls": []}]}
    return item, cached, publication.post_source(item, cached)


def occurrence_decision(src, *, kind, role, title, starts_at, ends_at=None, all_day=False, field="caption"):
    cited = evidence(field, src["texts"][field])
    return {"kind": kind, "date_role": role, "reason": "Saved decision from the audited run.",
            "activity_evidence": cited, "date_evidence": cited, "use_source_occurrences": False,
            "schedule": None, "occurrences": [{
                "title": title, "starts_at": starts_at, "ends_at": ends_at, "all_day": all_day,
                "location": "", "location_evidence": [], "activity_evidence": cited, "date_evidence": cited}]}


def rows_for(item, cached, src, result):
    assess.validate(result, src)
    payload = {"status": "complete", "result": result, "source": src}
    return publication.post_rows(item, cached, payload, {}, NOW)[0]


class FundraisingRoleTests(unittest.TestCase):
    def test_a_board_application_for_a_fundraising_chair_publishes_its_deadline(self):
        item, cached, src = caption_post(REACH, media_id="3992044593818549446",
                                         posted_at="2026-09-22T20:27:01+00:00",
                                         handle="thereachinitiative.ucr")
        rows = rows_for(item, cached, src, occurrence_decision(
            src, kind="deadline", role="cutoff", title="Application Deadline for Reach Initiative Board Positions",
            starts_at="2026-10-01T23:59:00-07:00"))
        self.assertEqual(["student_deadline"], [row["content_kind"] for row in rows])

    def test_officer_roles_do_not_make_a_fundraiser(self):
        for description in ("Now hiring a Fundraising Chair and a Treasurer.",
                            "Apply to be our VP of Fundraising!",
                            "Our fundraising committee meets weekly."):
            with self.subTest(description=description):
                self.assertEqual("student_deadline", classify_content_kind(
                    "instagram", title="Board Applications Due", description=description,
                    assessed_kind="deadline"))

    def test_advertised_fundraisers_are_still_excluded(self):
        for title, description in (("Boba Night", "Our fundraising chair is hosting a boba fundraiser!"),
                                   ("Chipotle Night", "Fundraising Chair here: 33% of proceeds go to our trip."),
                                   ("Fundraising Night", ""),
                                   ("Bake Sale", "Stop by the bell tower.")):
            with self.subTest(title=title):
                self.assertEqual("fundraiser", classify_content_kind(
                    "instagram", title=title, description=description, assessed_kind="activity"))


class RelativeWeekdayTests(unittest.TestCase):
    def source(self, text, posted_at="2026-09-23T16:09:16+00:00"):
        return {"source_key": "instagram:post:1", "origin": "instagram", "posted_at": posted_at,
                "texts": {"caption": text}, "source_occurrences": []}

    def test_this_friday_counts_from_the_pacific_publication_date(self):
        src = self.source(RCARD)  # Wednesday, September 23, 9:09 AM Pacific
        self.assertTrue(assess._day_supported(date(2026, 9, 25), RCARD, src))
        for other in (date(2026, 9, 24), date(2026, 10, 2), date(2026, 9, 18)):
            self.assertFalse(assess._day_supported(other, RCARD, src), other)

    def test_the_saved_rcard_deadline_now_validates(self):
        src = self.source(RCARD)
        result = occurrence_decision(src, kind="deadline", role="cutoff", title="R'Card Pickup Deadline",
                                     starts_at="2026-09-25T16:00:00-07:00")
        self.assertEqual(result, assess.validate(copy.deepcopy(result), src))

    def test_unqualified_or_ambiguous_weekdays_stay_unsupported(self):
        for text in ("Pick it up by 4 PM Friday!", "Pick it up by 4 PM next Friday!",
                     "Pick it up by 4 PM Fri"):
            with self.subTest(text=text):
                for day in (date(2026, 9, 25), date(2026, 10, 2)):
                    self.assertFalse(assess._day_supported(day, text, self.source(text)))

    def test_weekday_abbreviations_and_the_publication_day_itself(self):
        cases = (("Meet us this Wed!", date(2026, 9, 23)), ("This coming Thurs at noon", date(2026, 9, 24)),
                 ("THIS SUNDAY", date(2026, 9, 27)), ("this Tuesday", date(2026, 9, 29)))
        for text, day in cases:
            with self.subTest(text=text):
                self.assertTrue(assess._day_supported(day, text, self.source(text)))

    def test_an_evening_post_resolves_from_its_local_date_not_utc(self):
        # 8:06 PM Tuesday in Riverside is already Wednesday in UTC.
        src = self.source(NORTH_DISTRICT, posted_at="2026-09-23T03:06:09+00:00")
        result = occurrence_decision(src, kind="activity", role="occurrence",
                                     title="Love Island North District Field Day",
                                     starts_at="2026-09-24T17:00:00-07:00", ends_at="2026-09-24T19:30:00-07:00")
        with self.assertRaisesRegex(ValueError, "Tuesday, September 22, 2026"):
            assess.validate(copy.deepcopy(result), src)
        result["occurrences"][0].update(starts_at="2026-09-23T17:00:00-07:00", ends_at="2026-09-23T19:30:00-07:00")
        assess.validate(result, src)
        src["texts"]["caption"] = "Field day this Wednesday, 5 PM - 7:30 PM"
        self.assertTrue(assess._day_supported(date(2026, 9, 23), src["texts"]["caption"], src))

    def test_the_prompt_states_the_local_publication_date_without_changing_the_source(self):
        src = self.source(NORTH_DISTRICT, posted_at="2026-09-23T03:06:09+00:00")
        before = assess.fingerprint(src)
        result = occurrence_decision(src, kind="activity", role="occurrence",
                                     title="Love Island North District Field Day",
                                     starts_at="2026-09-23T17:00:00-07:00", ends_at="2026-09-23T19:30:00-07:00")
        with patch.object(assess, "_generate", return_value=SimpleNamespace(
                parsed=result, text=json.dumps(result), usage_metadata=None)) as generate:
            assess.assess(src)
        self.assertIn("Local publication date (never an event date by itself): "
                      "Tuesday, September 22, 2026", generate.call_args.args[0])
        self.assertEqual(before, assess.fingerprint(src))


class RegistrationTests(unittest.TestCase):
    def test_the_fall_involvement_fair_does_not_require_registration(self):
        item, cached, src = caption_post(FAIR, media_id="3992616370000457243",
                                         posted_at="2026-09-23T15:24:10+00:00", handle="ucrstudentlife")
        rows = rows_for(item, cached, src, occurrence_decision(
            src, kind="activity", role="occurrence", title="Fall Involvement Fair",
            starts_at="2026-09-30T00:00:00-07:00", ends_at="2026-10-01T00:00:00-07:00", all_day=True))
        self.assertFalse(rows[0]["rsvp_required"])

    def test_waived_requirements_and_bare_bio_links_are_not_signups(self):
        for text in ("No registration required just show up!", "Registration is not required.",
                     "No need to RSVP", "You don’t need to register", "RSVPs optional",
                     "WATCH IN THE F1 UCR DISCORD LINK IN BIO", "Read the full press release. Link in bio."):
            with self.subTest(text=text):
                self.assertFalse(_requires_signup(text))

    def test_stated_requirements_still_count(self):
        for text in ("Reservation Link in Bio (space is limited)", "reserved tickets are required",
                     "Don’t forget to register!", "No cost, registration required",
                     "No tickets needed. RSVP required.", "Sign up at the link in bio"):
            with self.subTest(text=text):
                self.assertTrue(_requires_signup(text))


class CategoryTests(unittest.TestCase):
    def test_the_advertised_performance_outweighs_an_interview_mention(self):
        self.assertEqual("arts", infer_category_from_text(
            "Joel Mejia Smith performance: “It’s been a while…”",
            "Joel Mejia Smith, Professor of Dance at UC Riverside, talks about his relationship with "
            "loneliness and his art. His performance “It’s been a while…” is Saturday, Sept 26, at the "
            "Culver Center of the Arts. Watch the full interview on the KUCR YouTube channel"))

    def test_a_dance_workshop_is_arts(self):
        self.assertEqual("arts", infer_category_from_text(
            "909DT Pre-Audition Workshop with Aamyah Davis",
            "Next up for our pre-audition workshops, we welcome Aamyah Davis! Workshop will again, be held "
            "at the UCR SRC Walkway on Wednesday 9/23 at 8PM and is completely FREE! Dancers of all levels "
            "are welcome!!"))

    def test_career_workshops_and_interview_practice_stay_career(self):
        for title in ("Resume Workshop", "Mock Interviews with Recruiters", "LinkedIn Workshop",
                      "Interviewing skills workshop"):
            with self.subTest(title=title):
                self.assertEqual("career", infer_category_from_text(title, ""))


class RecapTests(unittest.TestCase):
    def test_a_thank_you_for_a_finished_hike_is_not_published(self):
        item, cached, src = caption_post("thank you for participating 💕", media_id="3992094751989356925",
                                         posted_at="2026-09-22T22:08:40+00:00", handle="ucr_gsba",
                                         ocr="Welcome week 2026\nMount Rubidoux hike\n9/21/26")
        result = occurrence_decision(src, kind="activity", role="occurrence", title="Mount Rubidoux hike",
                                     starts_at="2026-09-21T00:00:00-07:00", ends_at="2026-09-22T00:00:00-07:00",
                                     all_day=True, field="slide_1_ocr")
        self.assertEqual([], rows_for(item, cached, src, result))
        # Without the thanks, the same late post stays inside the stale-date grace.
        item, cached, src = caption_post("", media_id="3992094751989356925",
                                         posted_at="2026-09-22T22:08:40+00:00", handle="ucr_gsba",
                                         ocr="Welcome week 2026\nMount Rubidoux hike\n9/21/26")
        self.assertEqual(1, len(rows_for(item, cached, src, result)))

    def test_thanks_that_announce_the_next_event_still_publish(self):
        caption = "Thanks to everyone who came to our first GBM! Next up: Beach Day on September 26, 2026."
        item, cached, src = caption_post(caption, media_id="3992094751989356999",
                                         posted_at="2026-09-22T22:08:40+00:00")
        rows = rows_for(item, cached, src, occurrence_decision(
            src, kind="activity", role="occurrence", title="Beach Day",
            starts_at="2026-09-26T00:00:00-07:00", ends_at="2026-09-27T00:00:00-07:00", all_day=True))
        self.assertEqual(["Beach Day"], [row["title"] for row in rows])


class DuplicateTests(unittest.TestCase):
    def rows(self, *suffixes):
        return [copy.deepcopy(row) for row_id, row in ROWS.items() if row_id.endswith(suffixes)]

    def converges(self, rows, removed_ids, winner_id):
        expected = plan(rows)
        updates, removed, replacements = expected
        self.assertEqual(set(removed_ids), removed)
        self.assertEqual({winner_id}, set(replacements.values()))
        for ordered in itertools.permutations(rows):
            self.assertEqual(expected, plan(list(ordered)))
        survivors = {r['id']: r for r in rows if r['id'] not in removed} | {r['id']: r for r in updates}
        self.assertEqual(([], set(), {}), plan(list(survivors.values())))

    def test_interview_excerpts_merge_into_the_organizers_timed_performance(self):
        organizer, first, second = 'ig_bluejadeandjoel_p3981934097668906335', \
            'ig_kucr883fm_p3992123687598225649', 'ig_kucr883fm_p3992721570257688767'
        self.converges([copy.deepcopy(ROWS[i]) for i in (organizer, first, second)], {first, second}, organizer)
        # The second excerpt reaches the organizer's listing only through the first.
        self.assertFalse(same_event(ROWS[second], ROWS[organizer]))
        self.assertTrue(same_event(ROWS[first], ROWS[second]))

    def test_the_legacy_midnight_story_is_left_for_source_review(self):
        rows = [copy.deepcopy(row) for row in ROWS.values() if 'joel' in row['title'].casefold()]
        self.assertNotIn('ig_bluejadeandjoel_20260926T0700Z', plan(rows)[1])

    def test_an_unquoted_or_relocated_teaser_stays_separate(self):
        organizer = ROWS['ig_bluejadeandjoel_p3981934097668906335']
        teaser = ROWS['ig_kucr883fm_p3992123687598225649']
        for changes in (dict(location='HUB 302'), dict(title='Joel Mejia Smith: New Work'),
                        dict(starts_at='2026-09-27T07:00:00+00:00', ends_at='2026-09-28T07:00:00+00:00')):
            with self.subTest(changes=changes):
                self.assertFalse(same_event(teaser | changes, organizer))

    def test_clubs_relaying_one_deadline_and_form_merge(self):
        greenwood, gaming = 'ig_greenwoodanimeclub_p3986884515990135541', 'ig_hlg_ucr_p3986944079131919785'
        rows = [copy.deepcopy(ROWS[i]) for i in (greenwood, gaming)]
        removed = plan(rows)[1]
        self.assertEqual(1, len(removed))
        (winner,) = {greenwood, gaming} - removed
        self.converges(rows, removed, winner)
        for changes in (dict(rsvp_url='https://forms.gle/another'), dict(rsvp_url=None),
                        dict(starts_at='2026-09-26T07:00:00+00:00', ends_at='2026-09-27T07:00:00+00:00')):
            with self.subTest(changes=changes):
                self.assertFalse(same_event(rows[0], rows[1] | changes))

    def test_a_post_about_one_event_outranks_the_same_session_in_a_schedule(self):
        # SWE, 2026-09-24: "Movie Night" from the welcome-week schedule would
        # have replaced the dedicated "SWE Movie Night: Big Hero 6" post.
        dedicated = copy.deepcopy(ROWS['ig_bluejadeandjoel_p3981934097668906335'])
        session = dedicated | {"id": "ig_bluejadeandjoel_p3990000000000000000-20260927T0200Z",
                               "description": dedicated["description"] + " Also this week: open studio, DJ night."}
        self.converges([dedicated, session], {session["id"]}, dedicated["id"])

    def test_a_same_account_teaser_quoted_by_the_official_flyer_merges(self):
        teaser, official = 'ig_hznupes_p3954373440643336519', 'ig_hznupes_p3976807495708125337'
        self.converges([copy.deepcopy(ROWS[i]) for i in (teaser, official)], {teaser}, official)
        for changes in (dict(host_handle='another_club'), dict(location='HUB 302'),
                        dict(title='Kappa Halloween Afterparty')):
            with self.subTest(changes=changes):
                self.assertFalse(same_event(ROWS[teaser] | changes, ROWS[official]))


class ReconciledRepublicationTests(unittest.TestCase):
    """A reconciled repeat advertisement is not recreated on every run."""

    def update(self, row, assessment="decision"):
        return {"source_key": f"instagram:post:{row['id'].rsplit('_p', 1)[1]}", "origin": "instagram",
                "assessment": {"status": "complete", "result": assessment}, "rows": [copy.deepcopy(row)],
                "known_event_ids": []}

    def remapped(self, update, canonical_id):
        return {update["source_key"]: {"assessment": copy.deepcopy(update["assessment"]),
                                       "event_ids": [canonical_id],
                                       "known_event_ids": sorted({update["rows"][0]["id"], canonical_id})}}

    def setUp(self):
        self.organizer = copy.deepcopy(ROWS['ig_bluejadeandjoel_p3981934097668906335'])
        self.first = copy.deepcopy(ROWS['ig_kucr883fm_p3992123687598225649'])
        self.second = copy.deepcopy(ROWS['ig_kucr883fm_p3992721570257688767'])
        self.live = {self.organizer["id"]: self.organizer}
        self.updates = [self.update(self.organizer), self.update(self.first), self.update(self.second)]
        self.registry = {self.updates[0]["source_key"]: {
            "assessment": self.updates[0]["assessment"], "event_ids": [self.organizer["id"]],
            "known_event_ids": [self.organizer["id"]]}}
        for update in self.updates[1:]:
            self.registry.update(self.remapped(update, self.organizer["id"]))

    def withheld(self, updates=None, live=None):
        stats = {}
        kept = publication._withhold_reconciled(copy.deepcopy(updates or self.updates), self.registry,
                                                self.live if live is None else live, stats)
        return [row["id"] for update in kept for row in update["rows"]], stats, kept

    def test_unchanged_repeats_are_withheld_including_transitive_ones(self):
        published, stats, _ = self.withheld()
        self.assertEqual([self.organizer["id"]], published)
        self.assertEqual({"reconciled_duplicates_skipped": 2}, stats)

    def test_a_changed_decision_republishes(self):
        updates = copy.deepcopy(self.updates)
        updates[1]["assessment"]["result"] = "corrected"
        published, _, _ = self.withheld(updates)
        # The second excerpt no longer has a withheld bridge to the organizer.
        self.assertEqual([self.organizer["id"], self.first["id"], self.second["id"]], published)

    def test_a_missing_canonical_listing_republishes(self):
        published, stats, _ = self.withheld(live={})
        self.assertEqual(3, len(published))
        self.assertEqual({}, stats)

    def test_a_row_that_no_longer_matches_its_listing_republishes(self):
        updates = copy.deepcopy(self.updates)
        for update in updates[1:]:
            update["rows"][0].update(starts_at="2026-10-03T07:00:00+00:00", ends_at="2026-10-04T07:00:00+00:00")
        published, _, _ = self.withheld(updates)
        self.assertEqual(3, len(published))

    def test_the_canonical_row_keeps_details_merged_from_withheld_repeats(self):
        updates = copy.deepcopy(self.updates)
        updates[0]["rows"][0]["has_free_food"] = False
        updates[1]["rows"][0]["has_free_food"] = True
        _, _, kept = self.withheld(updates)
        row = kept[0]["rows"][0]
        self.assertTrue(row["has_free_food"])
        self.assertNotIn("hosts", row)

    def session_post(self, *, supported):
        """KUCR's post listing three sessions; the performance was merged into the organizer's."""
        media = "3992123687598225649"
        merged = copy.deepcopy(self.first) | {"id": f"ig_kucr883fm_p{media}-20260926T0700Z"}
        others = [copy.deepcopy(self.first) | {"id": f"ig_kucr883fm_p{media}-{stamp}", "title": title,
                                               "starts_at": start, "ends_at": None, "location": "KUCR Studio"}
                  for stamp, title, start in (("20261001T0200Z", "KUCR Open Studio", "2026-10-01T02:00:00+00:00"),
                                              ("20261008T0200Z", "DJ Training Night", "2026-10-08T02:00:00+00:00"))]
        update = {"source_key": f"instagram:post:{media}", "origin": "instagram",
                  "assessment": {"status": "complete", "result": "sessions"},
                  "rows": [*others, merged], "known_event_ids": []}
        own = [row["id"] for row in update["rows"]]
        registry = {self.updates[0]["source_key"]: self.registry[self.updates[0]["source_key"]],
                    update["source_key"]: {"assessment": copy.deepcopy(update["assessment"]),
                                           "event_ids": supported(own, self.organizer["id"]),
                                           "known_event_ids": [*own, self.organizer["id"]]}}
        return [copy.deepcopy(self.updates[0]), update], registry, merged

    def withheld_sessions(self, updates, registry, live=None):
        stats = {}
        kept = publication._withhold_reconciled(updates, registry, self.live if live is None else live, stats)
        return {update["source_key"]: [row["id"] for row in update["rows"]] for update in kept}, stats

    def test_a_merged_session_is_withheld_while_its_siblings_publish(self):
        # Right after reconciliation remapped it, and on every run after that.
        for supported in (lambda own, organizer: [*own[:2], organizer], lambda own, organizer: own[:2]):
            with self.subTest(supported=supported):
                updates, registry, merged = self.session_post(supported=supported)
                published, stats = self.withheld_sessions(updates, registry)
                self.assertEqual({updates[0]["source_key"]: [self.organizer["id"]],
                                  updates[1]["source_key"]: [row["id"] for row in updates[1]["rows"][:2]]},
                                 published)
                self.assertEqual({"reconciled_duplicates_skipped": 1}, stats)

    def test_a_session_is_not_withheld_when_only_its_post_keeps_the_listing_alive(self):
        updates, registry, merged = self.session_post(supported=lambda own, organizer: [*own[:2], organizer])
        del registry[updates[0]["source_key"]]
        published, _ = self.withheld_sessions(updates[1:], registry)
        self.assertIn(merged["id"], published[updates[1]["source_key"]])
        # A locked listing is never retired, so withholding is safe again.
        published, _ = self.withheld_sessions(updates[1:], registry,
                                              live={self.organizer["id"]: self.organizer | {"is_locked": True}})
        self.assertNotIn(merged["id"], published[updates[1]["source_key"]])

    def test_sessions_of_one_post_never_merge_even_at_the_same_start(self):
        updates, _, merged = self.session_post(supported=lambda own, organizer: own)
        sibling = copy.deepcopy(merged) | {"id": merged["id"] + "-a1b2c3", "title": "Joel Mejia Smith: Encore"}
        self.assertFalse(same_event(merged, sibling))
        # The same session published by the post's owner and coauthor is one event.
        self.assertTrue(same_event(merged, merged | {"id": merged["id"].replace("kucr883fm", "ucrarts")}))
        self.assertTrue(same_event(merged, self.organizer))

    def test_publication_reads_listings_a_session_post_only_knows(self):
        media = "3992123687598225649"
        sessions = [f"ig_kucr883fm_p{media}-20261001T0200Z", f"ig_kucr883fm_p{media}-20260926T0700Z"]
        registry = {f"instagram:post:{media}": {
            "assessment": {"result": {"occurrences": [{}, {}], "schedule": None}},
            "event_ids": sessions[:1], "known_event_ids": [*sessions, self.organizer["id"]]}}
        with patch("db.get_event_rows_by_ids", return_value=[self.organizer]) as fetch:
            publication._canonical_listings([({"media_id": media}, {})], registry)
        fetch.assert_called_once_with([self.organizer["id"]])

    def test_publication_reads_only_listings_that_posts_were_remapped_onto(self):
        processed = [({"media_id": "3992123687598225649"}, {}), ({"media_id": "3981934097668906335"}, {})]
        registry = {"instagram:post:3992123687598225649": {"event_ids": [self.organizer["id"]]},
                    "instagram:post:3981934097668906335": {"event_ids": [self.organizer["id"]]}}
        with patch("db.get_event_rows_by_ids", return_value=[self.organizer]) as fetch:
            self.assertEqual({self.organizer["id"]: self.organizer},
                             publication._canonical_listings(processed, registry))
        fetch.assert_called_once_with([self.organizer["id"]])
        with patch("db.get_event_rows_by_ids") as fetch:
            self.assertEqual({}, publication._canonical_listings(processed[1:], registry))
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
