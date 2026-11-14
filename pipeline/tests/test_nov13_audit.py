"""Duplicates left on the site on November 13 that a venue spelling or a
sign-up link kept apart.

The rows are the public listings as the site served them; all_day is inferred
from a local-midnight start and end, since the public reader omits it.
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import reconcile_events as reconcile

CASES = json.loads((Path(__file__).parent / 'fixtures/nov13-duplicates.json').read_text())


def place(a, b):
    return reconcile._same_place({'location': a}, {'location': b})


class VenueSpellingTests(unittest.TestCase):
    def test_one_occasion_written_with_two_spellings_of_its_venue_merges(self):
        # APSP (244 Costo Hall) / APSP CENTER 244 COSTO; SSB 2nd Floor, The UE
        # / The UE, 2nd Floor Student Services Bldg.; School of Business
        # Building, Room 202 / SBB RM 202; SSB Lawn / Student Services
        # Building Lawn; SBB Finance Lab, in a caption crediting the co-host.
        for name in ('candle', 'coro', 'agsm', 'calfresh', 'finance_lab'):
            with self.subTest(name=name):
                rows = CASES[name]
                self.assertEqual('same', reconcile._same_place(*rows))
                expected = reconcile.plan(rows)
                self.assertEqual(1, len(expected[2]))
                for ordered in itertools.permutations(rows):
                    self.assertTrue(reconcile.same_event(*ordered))
                    self.assertEqual(expected, reconcile.plan(list(ordered)))

    def test_building_abbreviations_name_their_buildings(self):
        for a, b in (('SSB 2nd Floor', '2nd Floor of Student Services Bldg.'),
                     ('SSB Lawn', 'Student Services Building Lawn'),
                     ('SBB 202', 'School of Business Building, Room 202'),
                     ('SBB Finance Lab', 'Finance Lab, School of Business'),
                     ('APSP (244 Costo Hall)', 'APSP CENTER 244 COSTO')):
            with self.subTest(a=a, b=b):
                self.assertEqual('same', place(a, b))
                self.assertEqual('same', place(b, a))

    def test_rooms_wings_and_outdoor_spaces_still_separate(self):
        for a, b in (('Costo Hall 111', 'Costo Center 112'),
                     ('HUB 302 North', 'HUB 302 South'),
                     ('HUB 302 North', 'HUB 303 North'),
                     ('HUB Plaza', 'HUB 302'),
                     ('SSB Lawn', 'SSB 2nd Floor'),
                     ('SBB 202', 'SSB 202'),
                     ('Sproul Hall 1340', 'Olmsted Hall 1340'),
                     ('Hall', 'Center')):
            with self.subTest(a=a, b=b):
                self.assertEqual('conflicting', place(a, b))
                self.assertEqual('conflicting', place(b, a))
        # Psi Chi's and FFA's flyers print different rooms; left to review.
        self.assertFalse(reconcile.same_event(*CASES['lab_fair']))


class SignupLinkTests(unittest.TestCase):
    def test_a_root_address_whose_query_names_the_form_identifies_it(self):
        ours, theirs = CASES['scholarship']
        self.assertIsNotNone(reconcile._rsvp_identity(ours['rsvp_url']))
        self.assertEqual(reconcile._rsvp_identity(ours['rsvp_url']),
                         reconcile._rsvp_identity(theirs['rsvp_url']))
        self.assertTrue(reconcile.same_event(ours, theirs))
        self.assertTrue(reconcile.same_event(theirs, ours))
        self.assertEqual(1, len(reconcile.plan([ours, theirs])[2]))
        # Another scholarship on the same portal is another deadline.
        other = theirs | {'rsvp_url': theirs['rsvp_url'].replace('607387', '607388')}
        self.assertNotEqual(theirs['rsvp_url'], other['rsvp_url'])
        self.assertFalse(reconcile.same_event(ours, other))

    def test_a_bare_site_or_tracking_only_query_names_no_form(self):
        for url in ('https://ucr.scholarshipuniverse.com/', 'https://ucr.scholarshipuniverse.com',
                    'https://example.org/?utm_source=ig&fbclid=abc', 'ftp://example.org/?form=1', None, ''):
            self.assertIsNone(reconcile._rsvp_identity(url), url)
        # Two offices relaying R'Dream link only the portal's front page.
        self.assertFalse(reconcile.same_event(*CASES['rdream']))

    def test_tracking_parameters_do_not_change_a_form(self):
        self.assertEqual(reconcile._rsvp_identity('https://Example.org/?form=7&utm_source=ig'),
                         reconcile._rsvp_identity('https://example.org?fbclid=x&form=7'))
        self.assertEqual(reconcile._rsvp_identity('https://forms.gle/abc/'),
                         reconcile._rsvp_identity('https://forms.gle/abc?utm_medium=story'))


class ActivityAtAnOccasionTests(unittest.TestCase):
    def test_a_stall_at_the_fair_is_not_the_fair(self):
        fair, stall = CASES['faire']
        self.assertFalse(reconcile.same_event(fair, stall))
        # Nor when both posts spell the lawn the same way.
        for location in (fair['location'], stall['location']):
            rows = [fair | {'location': location}, stall | {'location': location}]
            for ordered in itertools.permutations(rows):
                self.assertFalse(reconcile.same_event(*ordered))
            self.assertEqual({}, reconcile.plan(rows)[2])

    def test_a_longer_name_for_the_fair_itself_still_merges(self):
        fair, stall = CASES['faire']
        relay = stall | {'title': 'ASPB Presents: Once Upon a Faire Fall Festival', 'location': fair['location']}
        self.assertTrue(reconcile.same_event(fair, relay))
        self.assertTrue(reconcile.same_event(relay, fair))

    def test_held_at_reads_which_side_of_at_names_the_occasion(self):
        occasion = {'once', 'upon', 'faire'}
        self.assertTrue(reconcile._held_at({'title': 'Depop at UCR Pop-up at Once Upon a Faire'}, occasion))
        self.assertTrue(reconcile._held_at({'title': 'Tarot Booth @ Once Upon a Faire'}, occasion))
        # The occasion is what is held, and "at" gives its venue.
        self.assertFalse(reconcile._held_at({'title': 'Once Upon a Faire at the Bell Tower'}, occasion))
        self.assertFalse(reconcile._held_at(
            {'title': 'CHASS Drop-in Academic Advising at LGBT Resource Center'}, {'chass', 'academic', 'advising'}))
        self.assertFalse(reconcile._held_at({'title': 'Once Upon a Faire'}, occasion))

    def test_a_club_booth_at_a_multiday_weekend_is_not_the_weekend(self):
        weekend = {'id': 'ig_ucralumni_p1', 'title': 'Highlander Family Weekend', 'host': 'UCR Alumni',
                   'host_handle': 'ucralumni', 'content_kind': 'student_event', 'all_day': True,
                   'starts_at': '2026-11-06T08:00:00+00:00', 'ends_at': '2026-11-09T08:00:00+00:00',
                   'location': '', 'source': 'instagram', 'description': ''}
        booth = weekend | {'id': 'ig_ucrbotany_p2', 'title': 'Plant Sale at Highlander Family Weekend',
                           'host': 'Botany Club', 'host_handle': 'ucrbotany'}
        relay = weekend | {'id': 'ig_ucrparents_p3', 'title': 'Highlander Family Weekend 2026',
                           'host': 'Parent Programs', 'host_handle': 'ucrparents'}
        self.assertFalse(reconcile.same_event(weekend, booth))
        self.assertFalse(reconcile.same_event(booth, weekend))
        self.assertTrue(reconcile.same_event(weekend, relay))


if __name__ == '__main__':
    unittest.main()
