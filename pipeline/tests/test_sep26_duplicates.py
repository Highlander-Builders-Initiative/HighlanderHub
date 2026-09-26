"""September 26 admin review decisions: the patterns the rules now reproduce, and the rest."""
import copy
import itertools
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reconcile_events import Reviews, plan, same_event

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/sep26-duplicates.json').read_text())
ROWS = {row['id']: row for row in FIXTURE['rows']}
DECISIONS = {frozenset((d['event_id'], d['other_event_id'])): d for d in FIXTURE['decisions']}


def rows(*ids):
    return [copy.deepcopy(ROWS[event_id]) for event_id in ids]


def decision(a, b):
    return DECISIONS[frozenset((a, b))]


# (kept, merged away) as the admin decided, now matched by a rule.
LEARNED = [
    # A schedule entry and the club's later post at the same start, retitled.
    ('ig_awwcucr_p3992906422932732771', 'ig_awwcucr_p3979182528484830981-20260929T0000Z'),
    # The same, moved to another room in the same building.
    ('ig_bsibucr_p3994269473225256935', 'ig_bsibucr_p3994144107382943814-20261001T0100Z'),
    # One multi-day occasion relayed by another account.
    ('ig_ucr_saa_p3982527289765956574', 'ig_ucriversideofficial_p3986151799102313494-20261106T0800Z'),
    # A legacy story whose title the account's timed post quotes.
    ('ig_bluejadeandjoel_p3981934097668906335', 'ig_bluejadeandjoel_20260926T0700Z'),
]
# The organizer keeps its listing and takes SSA's specific venue; the admin
# kept SSA's. Either reads the same on the site, and the admin's choice binds.
USM, SSA = 'ig_unitedsikhmovement_p3984337006174941028', 'ig_ssa_ucr_p3992176458381655610'
# Admin merges left to review: two shared words across accounts (Crosstown), a
# volunteer shift and the attendee program (Sequencing to Success, while the
# same shape for Latino Physician Day was judged different), and a both-undated
# pair whose rule would also merge two clubs' "First Day of School" photos.
STILL_REVIEWED = [
    ('ig_ucrwsoc_p3989236626873105735', 'ig_rivchamber_p3983234145506086926'),
    ('ig_ucrcnas_p3973775775959174619-20261003T1530Z', 'ig_dgog.ucr_p3993641131066430224-20261003T1500Z'),
    ('ig_ucralumni_p3976819441404675490', 'ig_ucrchass_20261107T0800Z'),
]


class LearnedDecisionTests(unittest.TestCase):
    def test_rules_keep_the_listing_the_admin_kept_in_every_order(self):
        for kept, merged in LEARNED:
            with self.subTest(kept=kept):
                self.assertEqual(kept, decision(kept, merged)['kept_event_id'])
                self.assertTrue(same_event(*rows(kept, merged)))
                expected = plan(rows(kept, merged))
                self.assertEqual({merged: kept}, expected[2])
                for ordered in itertools.permutations(rows(kept, merged)):
                    self.assertEqual(expected, plan(list(ordered)))

    def test_the_conference_merges_toward_its_organizer_with_the_named_venue(self):
        updates, removed, replacements = plan(rows(USM, SSA))
        self.assertEqual({SSA: USM}, replacements)
        self.assertEqual('University of Southern California', updates[0]['location'])
        # The recorded decision still binds this pair to the admin's choice.
        self.assertEqual({USM: SSA}, plan(rows(USM, SSA), reviews=Reviews({USM: SSA}))[2])

    def test_no_rule_contradicts_a_pair_judged_different(self):
        different = [pair for pair, d in DECISIONS.items() if d['status'] == 'different']
        self.assertEqual(6, len(different))
        for pair in different:
            with self.subTest(pair=sorted(pair)):
                self.assertFalse(same_event(*rows(*pair)))

    def test_ambiguous_merges_stay_with_the_admin(self):
        for pair in STILL_REVIEWED:
            with self.subTest(pair=pair):
                self.assertEqual('duplicate', decision(*pair)['status'])
                self.assertFalse(same_event(*rows(*pair)))


class ScheduleSupersededTests(unittest.TestCase):
    ENTRY, POST = 'ig_bsibucr_p3994144107382943814-20261001T0100Z', 'ig_bsibucr_p3994269473225256935'

    def test_another_live_schedule_entry_merges_into_its_post(self):
        entry, post = rows('ig_destinoucr_p3990810874210427760-20260924T0000Z', 'ig_destinoucr_p3992204304429550180')
        self.assertEqual({entry['id']: post['id']}, plan([entry, post])[2])

    def test_conflicts_still_keep_listings_apart(self):
        entry, post = rows(self.ENTRY, self.POST)
        for changes in [dict(location='WCH 205'), dict(starts_at='2026-10-01T01:30:00+00:00'),
                        dict(ends_at='2026-10-01T03:00:00+00:00'), dict(host_handle='other_club'),
                        dict(title='BSIB General Body Meeting 2027'),
                        # Two dedicated posts, or a schedule published after the post.
                        dict(id='ig_bsibucr_p3994144107382943814'),
                        dict(id='ig_bsibucr_p3999999999999999999-20261001T0100Z')]:
            with self.subTest(changes=changes):
                self.assertFalse(same_event(entry | changes, post))


class MultiDaySpanTests(unittest.TestCase):
    def test_a_different_span_or_an_own_name_title_stays_apart(self):
        saa, official = rows('ig_ucr_saa_p3982527289765956574',
                             'ig_ucriversideofficial_p3986151799102313494-20261106T0800Z')
        for changes in [dict(ends_at='2026-11-08T08:00:00+00:00'), dict(title='Family Weekend Brunch'),
                        dict(title='UCR Official Family Weekend Tailgate')]:
            with self.subTest(changes=changes):
                self.assertFalse(same_event(saa, official | changes))
        # "UC Riverside" names no particular venue; two named venues conflict.
        self.assertFalse(same_event(saa | {'location': 'HUB 302'}, official | {'location': 'Pentland Hills'}))


class QuotedStoryTests(unittest.TestCase):
    STORY, POST = 'ig_bluejadeandjoel_20260926T0700Z', 'ig_bluejadeandjoel_p3981934097668906335'

    def test_the_story_needs_its_own_account_day_and_quoted_title(self):
        story, post = rows(self.STORY, self.POST)
        for changes in [dict(host_handle='ucr_dance'), dict(title='Joel Mejia Smith: New Work'),
                        dict(starts_at='2026-09-27T07:00:00+00:00'), dict(source_url='https://www.instagram.com/p/X/'),
                        dict(all_day=True)]:
            with self.subTest(changes=changes):
                self.assertFalse(same_event(story | changes, post))

    def test_other_clubs_undated_look_alikes_stay_apart(self):
        for pair in [('ig_mescucr_p3989947685683569724', 'ig_bmesatucr_p3986177002404201805'),
                     ('ig_csp_ucr_p3993524520581505307', 'ig_mescucr_p3990837502209949756')]:
            with self.subTest(pair=pair):
                self.assertFalse(same_event(*rows(*pair)))


if __name__ == '__main__':
    unittest.main()
