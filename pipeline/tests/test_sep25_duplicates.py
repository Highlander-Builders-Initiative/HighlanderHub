"""September 25 production duplicates: repeats identified by their exact slot."""
import copy
import itertools
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reconcile_events import _place_words, plan, review_candidates, same_event

ROWS = {row['id']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/sep25-duplicates.json').read_text())}


def rows(*ids):
    return [copy.deepcopy(ROWS[event_id]) for event_id in ids]


# Canonical listing first, then the repeats it absorbs.
GROUPS = [
    # A schedule post's line and the event's own post, renamed.
    ('ig_designingdreamsucr_p3991578622329622598',
     'ig_designingdreamsucr_p3991225804188653761-20260925T2300Z'),
    # The schedule listed the room as TBA.
    ('ig_swe.ucr_p3993556542925612148', 'ig_swe.ucr_p3992713400886284255-20260926T0100Z'),
    ('ig_aspucr_p3993570775620427084', 'ig_aspucr_p3993566247290638031-20261001T0030Z'),
    ('ig_ucr_school_of_medicine_p3966694133183853797-20261002T1600Z',
     'ig_ucr_school_of_medicine_p3983998816458656668-20261002T1600Z'),
    # SSC 114 and Student Success Center 114.
    ('ig_ttsmatucr_p3991297852231143490', 'ig_ttsmatucr_p3986870303358473874-20261007T2200Z'),
    ('ig_thewellucr_p3993330773350533488', 'ig_thewellucr_p3981794780021667232'),
    # One venue named two ways by the same account.
    ('ig_ucr_gsba_p3992149601996509848', 'ig_ucr_gsba_p3990595040556201590-20260924T0100Z'),
    # Another account's post of the same occasion, in the same place.
    ('ig_ucrcecert_p3993450738252295097-20261006T1600Z',
     'ig_ucrextension_p3989132051631020922-20261006T1600Z'),
    ('ig_ucrcecert_p3993450738252295097-20261006T2000Z',
     'ig_ucrextension_p3989132051631020922-20261006T2000Z'),
    ('ig_ucrstudentlife_p3992616370000457243', 'ig_akakappatheta_p3991432452358300386-20260930T1700Z'),
    # A reposted deadline whose date was corrected: the newest post wins.
    ('ig_projectluxucr_p3993699260234309260', 'ig_projectluxucr_p3991650789138547733'),
]


class SameSlotTests(unittest.TestCase):
    def test_real_groups_converge_in_every_order_and_replay(self):
        for winner_id, *duplicate_ids in GROUPS:
            group = rows(winner_id, *duplicate_ids)
            expected = plan(group)
            updates, removed, replacements = expected
            self.assertEqual(dict.fromkeys(duplicate_ids, winner_id), replacements, winner_id)
            for ordered in itertools.permutations(group):
                self.assertEqual(expected, plan(list(ordered)))
            survivors = {r['id']: r for r in group if r['id'] not in removed}
            survivors.update({r['id']: r for r in updates})
            self.assertEqual(([], set(), {}), plan(list(survivors.values())))

    def test_the_whole_day_reconciles_to_one_listing_per_event(self):
        _, removed, _ = plan(list(copy.deepcopy(ROWS).values()))
        self.assertEqual({d for _, *duplicates in GROUPS for d in duplicates} | {
            'ig_swe.ucr_p3992822134405002764-20260929T0000Z'}, removed)

    def test_a_placeholder_room_takes_the_announced_one(self):
        schedule, announced = rows('ig_swe.ucr_p3992713400886284255-20260929T0000Z',
                                   'ig_swe.ucr_p3992822134405002764-20260929T0000Z')
        updates, removed, _ = plan([schedule, announced])
        self.assertEqual(1, len(removed))
        self.assertEqual('BOURNS A265', updates[0]['location'])

    def test_one_account_at_one_slot_still_respects_explicit_conflicts(self):
        a, b = rows('ig_ucr_gsba_p3992149601996509848', 'ig_ucr_gsba_p3990595040556201590-20260924T0100Z')
        for changes in [dict(location='HUB 302'), dict(ends_at='2026-09-24T04:00:00+00:00'),
                        dict(starts_at='2026-09-24T01:30:00+00:00'), dict(title='GSBA Mixer 2027'),
                        dict(title='GSBA Mixer Session 2'), dict(content_kind='student_deadline')]:
            self.assertFalse(same_event(a, b | changes), changes)
        rooms = [{'location': 'Costo Hall 111'}, {'location': 'Costo Hall 112'}]
        self.assertFalse(same_event(a | rooms[0], b | rooms[1]))

    def test_sessions_of_one_post_never_merge_even_at_one_slot(self):
        movie, painting = rows('ig_swe.ucr_p3992713400886284255-20260926T0100Z',
                               'ig_swe.ucr_p3992713400886284255-20260929T2200Z')
        painting.update(starts_at=movie['starts_at'], ends_at=movie['ends_at'], location=movie['location'])
        self.assertFalse(same_event(movie, painting))

    def test_a_bare_date_is_not_a_slot(self):
        # ACM's two deadlines share a day, and deadlines cluster at midnight.
        create, spark = rows('ig_acm_ucr_p3981465870551773335', 'ig_acm_ucr_p3980467437204327812')
        self.assertFalse(same_event(create, spark))
        timed = dict(all_day=False, starts_at='2026-09-26T06:59:00+00:00', ends_at='2026-09-26T07:00:00+00:00')
        self.assertFalse(same_event(create | timed, spark | timed))
        untimed = dict(content_kind='student_event', all_day=False)
        self.assertFalse(same_event(create | untimed, spark | untimed))

    def test_other_accounts_need_the_same_place_and_the_occasions_name(self):
        cecert, extension = rows('ig_ucrcecert_p3993450738252295097-20261006T1600Z',
                                 'ig_ucrextension_p3989132051631020922-20261006T1600Z')
        for changes in [dict(location=''), dict(location='HUB 302'),
                        dict(title='Clean Energy Resource Fair'), dict(title='CE-CERT Open House 2027')]:
            self.assertFalse(same_event(cecert, extension | changes), changes)
        # A club's table at the fair is its own listing, not a repost.
        fair, kdsap = rows('ig_ucrstudentlife_p3992616370000457243', 'ig_ucrkdsap_p3992840778807560105')
        self.assertFalse(same_event(fair, kdsap))
        # A region is not a venue; USM's two posts need review, not a title match.
        usm, ssa = rows('ig_unitedsikhmovement_p3984337006174941028', 'ig_ssa_ucr_p3992176458381655610')
        self.assertFalse(same_event(usm, ssa))

    def test_a_deadline_correction_needs_the_same_application(self):
        old, new = rows('ig_projectluxucr_p3991650789138547733', 'ig_projectluxucr_p3993699260234309260')
        updates, removed, _ = plan([old, new])
        self.assertEqual({old['id']}, removed)
        # The superseded date does not stretch the corrected deadline.
        self.assertEqual([], updates)
        # The newest date wins over a longer caption.
        self.assertEqual({old['id']}, plan([old | {'description': old['description'] * 2}, new])[1])
        # A timed correction without an end does not take the old date's end.
        timed_old = old | dict(all_day=False, starts_at='2026-10-26T06:59:00+00:00',
                               ends_at='2026-10-26T07:00:00+00:00')
        timed_new = new | dict(all_day=False, starts_at='2026-10-17T06:59:00+00:00', ends_at=None)
        updates, removed, _ = plan([timed_old, timed_new])
        self.assertEqual({old['id']}, removed)
        self.assertEqual([], updates)
        unrelated = dict(rsvp_url='https://forms.gle/other', description='Applications close soon.')
        for changes in [dict(title='Project Lux Volunteer Application Deadline'),
                        dict(host_handle='another_club'), unrelated,
                        dict(starts_at='2026-12-25T08:00:00+00:00', ends_at='2026-12-26T08:00:00+00:00'),
                        dict(content_kind='student_event')]:
            self.assertFalse(same_event(old | changes, new), changes)
        # The same caption with only its date changed identifies the application.
        self.assertTrue(same_event(old | {'rsvp_url': None}, new | {'rsvp_url': None}))

    def test_venue_spellings(self):
        for a, b in [('SSC 114', 'Student Success Center 114'), ('SSC114', 'SSC Room #114'),
                     ('Zoom', 'Virtual'), ('Online via Zoom', 'virtual'),
                     ('https://ucr.zoom.us/j/94905110', 'Zoom'), ('Pentland Bearcave', 'Pentland Bear Cave'),
                     ('By the Bell Tower', 'UCR Belltower'), ('WCH 127', 'Winston Chung Hall 127')]:
            self.assertEqual(_place_words({'location': a}), _place_words({'location': b}), (a, b))
        for placeholder in ('TBA', 'TBD', 'Room TBD', 'Invite Only', 'SoCal', 'UC Riverside'):
            self.assertEqual(set(), _place_words({'location': placeholder}), placeholder)


class ReviewCandidateTests(unittest.TestCase):
    def pairs(self, *ids, **kwargs):
        return {tuple(sorted((a['id'], b['id']))) for a, b in review_candidates(rows(*ids), **kwargs)}

    def test_unmerged_look_alikes_are_listed_once_merged_repeats_are_not(self):
        fair, kdsap, kappa = ('ig_ucrstudentlife_p3992616370000457243', 'ig_ucrkdsap_p3992840778807560105',
                              'ig_akakappatheta_p3991432452358300386-20260930T1700Z')
        self.assertEqual({tuple(sorted((fair, kdsap)))}, self.pairs(fair, kdsap))
        # The Kappa Theta repost merges, so it is not left for review.
        self.assertEqual(set(), self.pairs(fair, kappa))
        usm = ('ig_unitedsikhmovement_p3984337006174941028', 'ig_ssa_ucr_p3992176458381655610')
        self.assertEqual({tuple(sorted(usm))}, self.pairs(*usm))

    def test_boilerplate_deadlines_past_events_and_other_days_are_not_listed(self):
        self.assertEqual(set(), self.pairs('ig_acm_ucr_p3981465870551773335', 'ig_acm_ucr_p3980467437204327812'))
        usm = ('ig_unitedsikhmovement_p3984337006174941028', 'ig_ssa_ucr_p3992176458381655610')
        self.assertEqual(set(), self.pairs(*usm, now=datetime(2026, 12, 1, tzinfo=timezone.utc)))
        self.assertEqual(set(), self.pairs('ig_swe.ucr_p3992713400886284255-20260926T0100Z',
                                           'ig_swe.ucr_p3992713400886284255-20260929T2200Z'))


if __name__ == '__main__':
    unittest.main()
