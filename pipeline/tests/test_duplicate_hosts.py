"""Repeat advertisements must reconcile without losing time precision or hosts."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reconcile_events import plan, same_event


def gala(eid='ig_ucralumni_p3966553446651553037', **extra):
    return dict(id=eid, title='KUCR 60th Anniversary gala',
                starts_at='2026-10-02T07:00:00+00:00', ends_at='2026-10-03T07:00:00+00:00',
                all_day=True, location='The Alumni and Visitors Center, UC Riverside',
                host='UCR Alumni Association', host_handle='ucralumni', source='instagram',
                content_kind='student_event', has_free_food=False, is_locked=False) | extra


def celebration(**extra):
    return gala('ig_ucralumni_p3977498071100870455', title='KUCR 60th Anniversary Celebration',
                starts_at='2026-10-03T01:00:00+00:00', ends_at=None, all_day=False,
                location='UCR Alumni & Visitors Center') | extra


def tea_talk():
    teaser = gala('ig_aspucr_p3968032822924683079', title='3rd Annual Tea Talk: Black Identity',
                  description='Save the Date 🌿 Registration Opening Soon.',
                  starts_at='2026-09-22T07:00:00Z', ends_at='2026-09-23T07:00:00Z',
                  location='UC Riverside', host='UCR African Student Programs', host_handle='aspucr')
    timed = teaser | dict(id='ig_aspucr_p3973836307264072647', title='Tea Talk!: Black Identity',
                          description='Registration is NOW OPEN', all_day=False,
                          starts_at='2026-09-22T17:00:00Z', ends_at='2026-09-22T22:00:00Z',
                          location='Glasgow in Residential Dining', has_free_food=True,
                          rsvp_url='https://www.canvaqr.com/RGQsqaBoyH')
    return teaser, timed


class DuplicateHostsTests(unittest.TestCase):
    def test_tea_talk_teaser_merges_when_later_post_supplies_the_venue(self):
        teaser, timed = tea_talk()
        for rows in ([teaser, timed], [timed, teaser]):
            self.assertTrue(same_event(*rows))
            self.assertEqual(([], {teaser['id']}, {teaser['id']: timed['id']}), plan(rows))
        self.assertEqual(([], set(), {}), plan([timed]))

    def test_pending_venue_does_not_excuse_conflicting_or_weak_evidence(self):
        teaser, timed = tea_talk()
        for left, right in [
            (teaser, timed | {'title': '4th Annual Tea Talk: Black Identity'}),
            (teaser | {'title': 'Tea Talk 3: Black Identity'}, timed),
            (teaser | {'location': 'HUB 302'}, timed),
            (teaser | {'description': 'An event'}, timed),
            (teaser, timed | {'host_handle': 'different_club'}),
            (teaser | {'all_day': None}, timed),
            (teaser, timed | {'location': 'UC Riverside'}),
            (teaser | {'title': '3rd Annual Fall General Meeting'}, timed | {'title': 'Fall General Meeting'}),
        ]:
            with self.subTest(left=left, right=right):
                self.assertFalse(same_event(left, right))

    def test_pending_venue_keeps_ambiguous_sessions_and_admin_protections(self):
        teaser, timed = tea_talk()
        later = timed | {'id': 'ig_aspucr_p3', 'starts_at': '2026-09-22T23:00:00Z'}
        self.assertEqual(([], set(), {}), plan([teaser, timed, later]))
        self.assertEqual(([], {timed['id']}, {}), plan([timed], [teaser]))
        self.assertEqual(([], {timed['id']}, {timed['id']: teaser['id']}), plan([teaser | {'is_locked': True}, timed]))

    def test_actual_kucr_announcements_keep_six_pm_without_invented_end(self):
        rows = [gala(description='x' * 500), celebration()]
        before = copy.deepcopy(rows)
        for ordered in [rows, list(reversed(rows))]:
            self.assertTrue(same_event(*ordered))
            self.assertEqual(([], {rows[0]['id']}, {rows[0]['id']: rows[1]['id']}), plan(ordered))
        self.assertEqual(before, rows)

    def test_unconfirmed_midnight_different_dates_editions_venues_and_kinds_stay_separate(self):
        for changed in [gala(all_day=None), gala(all_day=False),
                        gala(title='KUCR 61st Anniversary gala'),
                        gala(location='Downtown Convention Center'),
                        gala(content_kind='student_deadline'),
                        gala(starts_at='2026-10-01T07:00:00Z'),
                        gala(ends_at='2026-10-05T07:00:00Z')]:
            self.assertFalse(same_event(changed, celebration()), changed)
        self.assertFalse(same_event(celebration(), celebration(starts_at='2026-10-03T03:00:00Z')))

    def test_generic_same_day_meetings_never_use_relaxed_time_matching(self):
        self.assertFalse(same_event(gala(title='Fall General Meeting'), celebration(title='Fall General Meeting')))

    def test_ambiguous_teaser_does_not_absorb_either_timed_session(self):
        rows = [gala(), celebration(), celebration(id='ig_ucralumni_p3', starts_at='2026-10-03T03:00:00Z')]
        self.assertEqual(([], set(), {}), plan(rows))

    def test_related_teasers_cannot_bridge_different_timed_sessions(self):
        rows = [gala(), gala('ig_ucralumni_p2', title='UCR KUCR 60th Anniversary gala'),
                celebration(), celebration(id='ig_ucralumni_p3', title='UCR KUCR 60th Anniversary Celebration',
                                             starts_at='2026-10-03T03:00:00Z')]
        updates, removed, replacements = plan(rows)
        self.assertNotIn(rows[2]['id'], removed)
        self.assertNotIn(rows[3]['id'], removed)

    def test_cross_club_matching_preserves_each_host_and_is_idempotent(self):
        a = celebration(description='longer canonical description')
        b = celebration(id='ig_partner_p42', host='Partner Club', host_handle='partner')
        updates, removed, replacements = plan([a, b])
        self.assertEqual({b['id']}, removed)
        self.assertEqual([{'host': a['host'], 'host_handle': 'ucralumni'},
                          {'host': 'Partner Club', 'host_handle': 'partner'}], updates[0]['hosts'])
        self.assertEqual(([], set(), {}), plan(updates))
        self.assertEqual(([], {b['id']}, {b['id']: a['id']}), plan([updates[0], b]))
        # Republishing primary fields must not discard saved partner hosts.
        c = celebration(id='ig_third_p43', host='Third Club', host_handle='third')
        self.assertEqual(3, len(plan([updates[0], c])[0][0]['hosts']))

    def test_short_distinctive_title_matches_with_a_shared_room(self):
        a = celebration(title='Study Jam', location='HUB 302')
        b = celebration(id='ig_partner_p42', title='Study Jam', location='HUB 302',
                        host='Partner Club', host_handle='partner')
        self.assertTrue(same_event(a, b))
        self.assertFalse(same_event(a, b | {'location': 'HUB 303'}))
        self.assertFalse(same_event(a | {'title': 'General Meeting'}, b | {'title': 'General Meeting'}))

    def test_same_account_aliases_and_anonymous_accounts_do_not_add_hosts(self):
        self.assertEqual([], plan([gala(), celebration(host='UCR Alumni')])[0])
        hidden = celebration(id='ig_highlander_opps_p1', host='Private', host_handle='highlander_opps')
        self.assertEqual([], plan([celebration(description='winner'), hidden])[0])

    def test_date_only_cross_club_match_needs_ownership_corroboration(self):
        partner = celebration(id='ig_partner_p42', host='Partner', host_handle='partner')
        self.assertFalse(same_event(gala(), partner))
        self.assertTrue(same_event(gala(), partner | {'description': 'Hosted with @ucralumni'}))

    def test_locks_and_tombstones_still_constrain_relaxed_matches(self):
        self.assertEqual(([], {celebration()['id']}, {celebration()['id']: gala()['id']}), plan([gala(is_locked=True), celebration()]))
        self.assertEqual(([], {celebration()['id']}, {}), plan([celebration()], [gala()]))
        self.assertEqual(([], set(), {}), plan([celebration(is_locked=True)], [gala()]))
