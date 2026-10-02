"""UCR TAPS's Ride to The Cheech: one trip at its check-in and its departure."""
import itertools
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import content_assessment as semantic
from reconcile_events import plan, same_event

SIGNUP = 'https://events.ucr.edu/event/ride-to-the-cheech'
# The flyer post's caption: 'Meet us at Bannockburn Village at 11:50 AM to check in'.
FLYER = {
    'id': 'ig_ucrtaps_p3997715456455231193-20261004T1850Z', 'title': 'Group Trip to The Cheech Museum',
    'description': 'Sunday, October 4th: Meet us at Bannockburn Village at 11:50 AM to check in before '
                   'we take the RTA Route 1 bus to The Cheech Museum in Downtown Riverside.',
    'starts_at': '2026-10-04T18:50:00+00:00', 'ends_at': '2026-10-05T00:00:00+00:00',
    'location': 'Bannockburn Village', 'host': 'UCR Transportation Services', 'host_handle': 'ucrtaps',
    'category': 'other', 'source': 'instagram', 'source_url': 'https://www.instagram.com/p/Dd6vQbfGkbZ/',
    'rsvp_url': SIGNUP, 'rsvp_required': False, 'is_locked': True, 'content_kind': 'student_event',
    'has_free_food': False, 'all_day': False, 'hosts': [],
}
# The monthly carousel's slide: 'We will leave UCR at 12 PM from Bannockburn Village'.
CAROUSEL = {
    'id': 'ig_ucrtaps_p3997897538102448491-20261004T1900Z', 'title': 'Ride to The Cheech',
    'description': 'Swipe to see our upcoming trips for October 2026',
    'starts_at': '2026-10-04T19:00:00+00:00', 'ends_at': None,
    'location': 'Bannockburn Village', 'host': 'UCR Transportation Services', 'host_handle': 'ucrtaps',
    'category': 'other', 'source': 'instagram', 'source_url': 'https://www.instagram.com/p/Dd7YqEPAVFr/',
    'rsvp_url': SIGNUP, 'rsvp_required': False, 'is_locked': False, 'content_kind': 'student_event',
    'has_free_food': False, 'all_day': False, 'hosts': [],
}


class CheckInOffsetTests(unittest.TestCase):
    def test_check_in_and_departure_are_one_trip(self):
        self.assertTrue(same_event(FLYER, CAROUSEL))
        self.assertTrue(same_event(CAROUSEL, FLYER))
        for rows in itertools.permutations([FLYER, CAROUSEL]):
            updates, removed, replacements = plan([dict(row) for row in rows])
            self.assertEqual({CAROUSEL['id']: FLYER['id']}, replacements)
            self.assertEqual([], updates)  # The locked listing is never rewritten.

    def test_unlocked_pair_converges(self):
        rows = [FLYER | {'is_locked': False}, dict(CAROUSEL)]
        updates, removed, replacements = plan(rows)
        self.assertEqual(1, len(removed))
        survivors = {r['id']: r for r in rows if r['id'] not in removed} | {r['id']: r for r in updates}
        self.assertEqual(([], set(), {}), plan(list(survivors.values())))

    def test_uncorroborated_offsets_stay_apart(self):
        for changes in [
            dict(rsvp_url=None),
            dict(rsvp_url='https://events.ucr.edu/event/bus-to-basics'),
            dict(host_handle='csp_ucr', host='Chicano Student Programs'),
            dict(location='Kim Wilcox Dr North & Aberdeen'),
            dict(starts_at='2026-10-04T19:30:00+00:00'),
            dict(ends_at='2026-10-04T23:00:00+00:00'),
            dict(title='Bus to Basics - Campus Route'),
            dict(title='Ride to The Cheech Session 2'),
        ]:
            self.assertFalse(same_event(FLYER, CAROUSEL | changes), changes)

    def test_sessions_of_one_post_never_merge(self):
        sibling = CAROUSEL | {'id': 'ig_ucrtaps_p3997715456455231193-20261004T1900Z'}
        self.assertFalse(same_event(FLYER, sibling))


class TripDestinationPromptTests(unittest.TestCase):
    def test_destination_program_is_not_a_second_occurrence(self):
        prompt = ' '.join(semantic.PROMPT.split())
        self.assertIn('A trip, outing or group ride to another place is one occurrence', prompt)
        self.assertIn('never a separate Zine Fest listing', prompt)


if __name__ == '__main__':
    unittest.main()
