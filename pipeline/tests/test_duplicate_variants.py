"""September 23 production duplicates and contradictory near matches."""
import copy
import itertools
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reconcile_events import plan, same_event

ROWS = json.loads((Path(__file__).parent / 'fixtures/duplicate-variants.json').read_text())


def group(prefix):
    return [copy.deepcopy(row) for row in ROWS if row['id'].startswith(prefix)]


class DuplicateVariantsTests(unittest.TestCase):
    def test_real_groups_converge_in_every_order_and_replay(self):
        for prefix, winner_id in [
            ('ig_popucr', 'ig_popucr_p3957338841803607814'),
            ('ig_mescucr', 'ig_mescucr_p3991305078040094301'),
            ('ig_ucr', 'ig_ucrmcnair_p3971684871794696064'),
        ]:
            rows = group(prefix)
            before = copy.deepcopy(rows)
            expected = plan(rows)
            updates, removed, replacements = expected
            self.assertEqual(len(rows) - 1, len(removed))
            self.assertEqual({winner_id}, set(replacements.values()))
            for ordered in itertools.permutations(rows):
                self.assertEqual(expected, plan(list(ordered)))
            survivors = {r['id']: r for r in rows if r['id'] not in removed}
            survivors.update({r['id']: r for r in updates})
            self.assertEqual(([], set(), {}), plan(list(survivors.values())))
            self.assertEqual(removed, plan(list(({r['id']: r for r in rows} | survivors).values()))[1])
            self.assertEqual(before, rows)
            if prefix == 'ig_ucr':
                self.assertTrue(survivors[winner_id]['rsvp_required'])
                self.assertEqual({'ucrmcnair', 'ucr_saa'},
                                 {h['host_handle'] for h in survivors[winner_id]['hosts']})

    def test_acronym_needs_full_name_and_matching_handle(self):
        a, b = group('ig_popucr')
        for changes in [dict(host_handle='another_club'),
                        dict(title='UCR POP Interview'), dict(title='UCR POP Conference 2027'),
                        dict(starts_at='2026-09-24T07:00:00Z'),
                        dict(ends_at='2026-09-25T07:00:00Z')]:
            self.assertFalse(same_event(a, b | changes), changes)
        # An arbitrary club's initials must not be invented as an alias.
        self.assertFalse(same_event(a | {'host_handle': 'campus_leaders'},
                                    b | {'host_handle': 'campus_leaders'}))
        self.assertFalse(same_event(a | {'host': 'Campus Leadership'},
                                    b | {'host': 'Campus Leadership'}))

    def test_center_shorthand_does_not_excuse_specific_conflicts(self):
        detailed, shorthand = group('ig_mescucr')
        for changes in [dict(location='MESC 112'), dict(location='Costo Hall 112'),
                        dict(location='HUB 302'), dict(host_handle='other_center'),
                        dict(title='MESC Leadership Workshop'),
                        dict(starts_at='2026-09-28T23:00:00Z'),
                        dict(ends_at='2026-09-29T01:00:00Z')]:
            self.assertFalse(same_event(detailed, shorthand | changes), changes)
        # Even when a longer caption wins, retain the corroborated actual room.
        shorthand['description'] = 'long caption ' * 100
        updates, _, replacements = plan([detailed, shorthand])
        self.assertEqual({detailed['id']: shorthand['id']}, replacements)
        self.assertEqual('Costo Hall 111', updates[0]['location'])

    def test_credited_deadlines_preserve_program_and_action(self):
        partner, first, reminder = group('ig_ucr')
        self.assertTrue(same_event(first, reminder))
        self.assertTrue(same_event(partner, first))
        for changes in [
            dict(description='Unrelated announcement'),
            dict(title='McNair Scholars Program Final Review Date'),
            dict(title='McNair Scholars Program Interview Date'),
            dict(title='McNair Scholars Program Scholarship First Review Date'),
            dict(title='Other Scholars Program First Review Date'),
            dict(title='McNair Scholars Program Second Review Date'),
            dict(title='McNair Scholars Program First Review Date 2027'),
            dict(content_kind='student_event'),
        ]:
            self.assertFalse(same_event(first, partner | changes), changes)
        self.assertFalse(same_event(first | {'title': 'First Review Date'},
                                    partner | {'title': 'First Review Date'}))

    def test_underspecified_posts_cannot_bridge_distinct_rooms_or_programs(self):
        detailed, shorthand = group('ig_mescucr')
        other_room = detailed | {'id': 'ig_mescucr_p123', 'source_url': '', 'location': 'Costo Hall 112'}
        conference, abbreviated = group('ig_popucr')
        other_program = conference | {'id': 'ig_popucr_p123', 'source_url': '',
                                      'title': 'Power of the Peers: Faculty Research Conference'}
        for rows in ([detailed, shorthand, other_room], [conference, abbreviated, other_program]):
            for ordered in itertools.permutations(rows):
                self.assertEqual(([], set(), {}), plan(list(ordered)))
            self.assertEqual(([], set(), {}), plan(rows[:2], [rows[2]]))

    def test_admin_protections_apply_to_each_new_match(self):
        for prefix in ('ig_popucr', 'ig_mescucr', 'ig_ucr'):
            a, b = group(prefix)[:2]
            self.assertEqual(([], {b['id']}, {}), plan([b], [a]))
            self.assertEqual(([], set(), {}), plan([b | {'is_locked': True}], [a]))
            self.assertEqual(([], {b['id']}, {b['id']: a['id']}),
                             plan([a | {'is_locked': True}, b]))


if __name__ == '__main__':
    unittest.main()
