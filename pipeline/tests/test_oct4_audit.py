"""Source-backed regressions from the October 4 pipeline audit."""
import itertools
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
import reconcile_events as reconcile

CASES = json.loads((Path(__file__).parent / 'fixtures/oct4-sources.json').read_text())
NOW = datetime(2026, 10, 4, 18, tzinfo=timezone.utc)


class SameAccountSlotTests(unittest.TestCase):
    def test_hospice_calendar_matches_its_earlier_timeline(self):
        night, rec_night, meeting, gm = CASES['hospice']
        for a, b in ((night, rec_night), (meeting, gm)):
            with self.subTest(a=a['title'], b=b['title']):
                self.assertTrue(reconcile.same_event(a, b))
                self.assertTrue(reconcile.same_event(b, a))
        # The locked timeline rows survive; the calendar's copies are retired.
        _, removed, remap = reconcile.plan(CASES['hospice'], now=NOW)
        self.assertEqual({rec_night['id']: night['id'], gm['id']: meeting['id']}, remap)
        self.assertEqual(set(remap), removed)

    def test_session_numbers_rooms_ends_and_owners_still_separate(self):
        _, _, meeting, gm = CASES['hospice']
        night, rec_night = CASES['hospice'][:2]
        for changed in (meeting | {'title': 'GM #2'}, meeting | {'location': 'HUB 268'},
                        meeting | {'ends_at': '2026-10-17T04:00:00+00:00'},
                        meeting | {'host_handle': 'another_club'},
                        meeting | {'starts_at': '2026-10-17T02:30:00+00:00'}):
            self.assertFalse(reconcile.same_event(changed, gm), changed)
        self.assertFalse(reconcile.same_event(night | {'location': 'HUB 302'}, rec_night))

    def test_recreation_center_spellings_name_one_venue(self):
        for location in ('Student Recreation Center', 'Student Rec Center', 'Rec Center', 'SRC @UCR'):
            self.assertEqual({'src'}, reconcile._place_words({'location': location}), location)
        self.assertEqual({'src', 'arena'}, reconcile._place_words({'location': 'SRC Arena'}))

    def test_ordinary_unnumbered_pairs_are_unchanged(self):
        # Without a number on either side, the stricter end check still holds.
        _, _, meeting, gm = CASES['hospice']
        self.assertFalse(reconcile._contradicting_titles(meeting, gm, numbered_once=True))
        self.assertTrue(reconcile._contradicting_titles(meeting, gm))
        self.assertTrue(reconcile._contradicting_titles(gm | {'title': 'GM #2'}, gm, numbered_once=True))


class CrossAccountOccasionTests(unittest.TestCase):
    def test_latin_heritage_night_relayed_by_three_accounts(self):
        rows = CASES['latin']
        for a, b in itertools.combinations(rows, 2):
            with self.subTest(a=a['id'], b=b['id']):
                self.assertTrue(reconcile.same_event(a, b))
        updates, removed, remap = reconcile.plan(rows, now=NOW)
        team = 'ig_ucrmsoccer_p4000308180839201313'
        self.assertEqual({row['id'] for row in rows} - {team}, removed)
        self.assertEqual({team}, set(remap.values()))
        self.assertEqual({'ucrmsoccer', 'csp_ucr', 'ucriversideofficial'},
                         {host['host_handle'] for host in updates[0]['hosts']})

    def test_participation_in_a_larger_occasion_stays_separate(self):
        performance, market = CASES['saf']
        self.assertFalse(reconcile.same_event(performance, market))

    def test_different_ends_venues_and_thin_titles_stay_separate(self):
        csp, athletics, team = CASES['latin']
        self.assertFalse(reconcile.same_event(csp, team | {'ends_at': '2026-10-08T04:00:00+00:00'}))
        self.assertFalse(reconcile.same_event(csp, team | {'location': 'SRC Arena'}))
        self.assertFalse(reconcile.same_event(csp | {'title': 'Heritage Night'}, team | {'title': 'Heritage Night Game'}))
        self.assertFalse(reconcile.same_event(athletics, team | {'starts_at': '2026-10-08T02:30:00+00:00'}))


class DeadlineTests(unittest.TestCase):
    def test_season_qualifier_does_not_name_another_cutoff(self):
        timed, dated = CASES['axo']
        self.assertTrue(reconcile.same_event(timed, dated))
        _, removed, remap = reconcile.plan(CASES['axo'], now=NOW)
        self.assertEqual({dated['id']: timed['id']}, remap)
        self.assertFalse(reconcile.same_event(timed | {'title': 'Spring recruitment registration deadline'},
                                              dated | {'title': 'Fall recruitment registration deadline'}))
        self.assertFalse(reconcile.same_event(timed, dated | {'title': 'Board application deadline'}))
        self.assertFalse(reconcile.same_event(timed, dated | {'host_handle': 'another_club'}))


class CategoryTests(unittest.TestCase):
    def test_member_profiles_do_not_choose_the_category(self):
        for name, title in (('csa_rgl', 'UCR CSA RGL Meet The Fams'), ('csa_bunnies', 'UCR CSA Bunnies Meet The Fams')):
            case = CASES[name]
            rows, _ = publication.post_rows(case['record'], case['cached'], case['assessment'], {}, '2026-10-04T07:00:00Z')
            self.assertEqual([title], [row['title'] for row in rows])
            self.assertEqual('other', rows[0]['category'], name)

    def test_profile_detection_needs_two_profile_labels(self):
        self.assertTrue(publication._member_profile('JADEN TSAI\nHOBBIES\nVolleyball, pickleball\nFUN FACT\nI studied abroad'))
        self.assertTrue(publication._member_profile('Year: 4th\nMajor: Biology\nCareer Aspiration: OB/GYN'))
        for text in ('Volleyball Tryouts\nHOBBIES fair', 'Major: Biology students welcome',
                     'FUN FACT NIGHT\nTrivia at 7 PM', 'Pickleball tournament\n5 PM at the SRC'):
            self.assertFalse(publication._member_profile(text), text)


if __name__ == '__main__':
    unittest.main()
