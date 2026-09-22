"""Real September 22 duplicate rows, plus near matches that must stay separate."""
import copy
import itertools
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db
from reconcile_events import _reconciliation_rows, plan, same_event

ROWS = json.loads((Path(__file__).parent / 'fixtures/repeated-announcements.json').read_text())


def group(term):
    return [copy.deepcopy(r) for r in ROWS if term in r['title'].casefold()]


class RepeatedAnnouncementsTests(unittest.TestCase):
    def test_named_live_duplicates_merge_in_every_input_order(self):
        for term, count in [('block party', 3), ('silent disglo', 3), ('rush', 2),
                            ('recruitment', 2), ('sdrc', 2)]:
            rows = group(term)
            self.assertEqual(count, len(rows))
            before = copy.deepcopy(rows)
            expected = plan(rows)
            for ordered in itertools.permutations(rows):
                self.assertEqual(expected, plan(list(ordered)))
            updates, removed, replacements = expected
            self.assertEqual(count - 1, len(removed))
            self.assertEqual(removed, set(replacements))
            self.assertEqual(1, len(set(replacements.values())))
            survivors = {r['id']: r for r in rows if r['id'] not in removed}
            survivors.update({r['id']: r for r in updates})
            self.assertEqual(([], set(), {}), plan(list(survivors.values())))
            # A later importer replay converges to the same survivor.
            replay = {r['id']: r for r in rows} | survivors
            self.assertEqual(removed, plan(list(replay.values()))[1])
            self.assertEqual(before, rows)

        reception = [copy.deepcopy(r) for r in ROWS if r['host_handle'] == 'ucrarts']
        updates, removed, replacements = plan(reception)
        self.assertEqual(2, len(removed))
        self.assertEqual({'ig_ucrarts_p3986353709796873976'}, set(replacements.values()))
        self.assertEqual('Fall Reception', updates[0]['title'])
        self.assertTrue(updates[0]['has_free_food'])
        self.assertTrue(updates[0]['rsvp_required'])

    def test_block_party_keeps_organizer_and_does_not_generalize_paid_graduate_signup(self):
        updates, removed, replacements = plan(group('block party'))
        winner = updates[0]
        self.assertEqual('ig_aspb_ucr_p3987699302558500071', winner['id'])
        self.assertEqual('Hub Lawn', winner['location'])
        self.assertFalse(winner['rsvp_required'])
        self.assertIsNone(winner['rsvp_url'])
        self.assertEqual({'aspb_ucr', 'ucrgradsuccess'}, {h['host_handle'] for h in winner['hosts']})
        self.assertTrue(all(r == winner['id'] for r in replacements.values()))

    def test_deadline_retains_registration_requirement(self):
        updates, _, _ = plan(group('rush'))
        self.assertTrue(updates[0]['rsvp_required'])

    def test_different_programs_and_deadline_actions_never_merge(self):
        self.assertEqual(([], set(), {}), plan(group('acm')))
        a, b = group('rush')
        for title in ['Alpha Epsilon Pi Scholarship Application Deadline',
                      'Alpha Epsilon Pi Rush Interview Deadline',
                      'Alpha Epsilon Pi Spring Rush Application Deadline']:
            self.assertFalse(same_event(a, b | {'title': title}))
        self.assertFalse(same_event(a, b | {'host_handle': 'another_fraternity'}))

    def test_optional_year_is_only_the_occurrence_year_and_conflicts_are_preserved(self):
        a, b = [r for r in group('silent disglo') if r['source'] == 'instagram']
        for changes in [{'title': 'Silent Disglo 2027'}, {'title': 'Silent Disglo Session 2'},
                        {'location': 'HUB 302'}, {'ends_at': '2026-09-30T05:00:00Z'},
                        {'starts_at': '2026-09-30T02:00:00Z'}, {'content_kind': 'student_deadline'}]:
            self.assertFalse(same_event(a, b | changes), changes)
        self.assertFalse(same_event(a, b | {'host_handle': 'another_club', 'location': ''}))

    def test_generic_cross_club_meetings_still_need_ownership(self):
        a, b = [r for r in group('silent disglo') if r['source'] == 'instagram']
        self.assertFalse(same_event(a | {'title': 'General Meeting 2026'},
                                   b | {'title': 'General Meeting', 'host_handle': 'other'}))

    def test_transitive_group_keeps_explicit_source_replacement(self):
        # The no-venue ASPB post does not directly match GradSuccess, but its
        # source still belongs to the same corroborated group if admin locks
        # select GradSuccess as the survivor.
        rows = group('block party')
        partner = next(r for r in rows if r['host_handle'] == 'ucrgradsuccess')
        partner['is_locked'] = True
        updates, removed, replacements = plan(rows)
        self.assertEqual([], updates)
        self.assertEqual(2, len(removed))
        self.assertEqual({partner['id']}, set(replacements.values()))
        self.assertEqual(removed, set(replacements))

    def test_admin_tombstones_and_locks_apply_to_new_matches(self):
        a, b = group('rush')
        self.assertEqual(([], {b['id']}, {}), plan([b], [a]))
        self.assertEqual(([], set(), {}), plan([b | {'is_locked': True}], [a]))
        self.assertEqual(([], {b['id']}, {b['id']: a['id']}), plan([a | {'is_locked': True}, b]))

    def test_acronyms_require_explicit_alias_evidence(self):
        a, b = [r for r in ROWS if r['host_handle'] == 'popucr']
        self.assertFalse(same_event(a, b))
        self.assertEqual(([], set(), {}), plan([a, b]))
        self.assertTrue(same_event(a | {'host': a['host'] + ' (POP)'}, b))
        for noun in ('Workshop', 'Meeting'):
            left = a | {'host': 'Example Club (EC)', 'title': f'Example Club Leadership {noun}'}
            right = b | {'host': 'Example Club (EC)', 'title': f'EC {noun}'}
            self.assertFalse(same_event(left, right))

    def test_two_word_teasers_only_relax_for_exact_same_account_repeats(self):
        a, b = group('rush')
        teaser = a | dict(title='Study Jam', content_kind='student_event', all_day=True,
                          starts_at='2026-09-27T07:00:00Z', ends_at='2026-09-28T07:00:00Z',
                          location='The Barn')
        timed = b | dict(title='Study Jam', content_kind='student_event', all_day=False,
                         starts_at='2026-09-27T20:00:00Z', ends_at=None, location='The Barn')
        self.assertTrue(same_event(teaser, timed))
        self.assertFalse(same_event(teaser | {'title': '3rd Annual Study Jam'}, timed))
        self.assertFalse(same_event(teaser, timed | {'host_handle': 'partner',
                                                    'description': '@aepi_ucr'}))
        self.assertFalse(same_event(teaser, timed | {'location': 'HUB 302'}))

    def test_account_normalization_is_shared_by_matching_and_signup_inheritance(self):
        a, b = group('rush')
        a = a | dict(host_handle=' @AEPI_UCR ', host='ALPHA EPSILON PI',
                     rsvp_required=False, has_free_food=True)
        b = b | dict(rsvp_required=True, has_free_food=False)
        updates, removed, replacements = plan([a, b])
        self.assertEqual({b['id']: a['id']}, replacements)
        self.assertEqual({b['id']}, removed)
        self.assertTrue(updates[0]['rsvp_required'])

    def test_legacy_only_and_tombstoned_campus_rows_are_not_removable(self):
        campus = group('silent disglo')[0]
        sibling = campus | {'id': 'ucr_events_2'}
        instagram = group('silent disglo')[1]
        self.assertEqual(([], set(), {}), plan([campus, sibling]))
        self.assertEqual(([], set(), {}), plan([campus], [sibling]))
        self.assertEqual(([], {instagram['id']}, {}), plan([campus, instagram], [sibling]))
        # A locked campus survivor is valid for Instagram removal, but cannot
        # authorize the removal of a second campus row.
        updates, removed, replacements = plan([campus | {'is_locked': True}, sibling, instagram])
        self.assertEqual(([], {instagram['id']}, {instagram['id']: campus['id']}),
                         (updates, removed, replacements))
        self.assertEqual(([], set(), {}), plan([campus, sibling | {'source': 'manual'}]))

    def test_notification_inheritance_uses_only_the_transitive_plan_map(self):
        import reconcile_events as reconcile
        rows = group('block party')
        partner = next(r for r in rows if r['host_handle'] == 'ucrgradsuccess')
        partner['is_locked'] = True
        updates, removed, replacements = plan(rows)
        source = next(r for r in rows if r['location'] == '')
        self.assertFalse(same_event(source, partner))
        database = Mock()
        database.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = [
            {'event_id': source['id'], 'kind': 'free_food', 'notified_at': '2026-09-01T12:00:00Z'}]
        with patch.object(db, 'client', return_value=database), \
             patch.object(reconcile, 'same_event', side_effect=AssertionError('Do not rematch')):
            reconcile._inherit_notifications(rows, updates, replacements)
        self.assertEqual(partner['id'], database.table.return_value.upsert.call_args.args[0][0]['event_id'])
        database.reset_mock()
        with patch.object(db, 'client', return_value=database), \
             patch.object(reconcile, 'same_event', side_effect=AssertionError('Do not rematch')):
            reconcile._inherit_notifications(rows, [], {})
        database.table.assert_not_called()

    def test_main_dispatches_plan_replacements_and_tombstones_without_rematching(self):
        import reconcile_events as reconcile
        rows = group('block party')
        partner = next(r for r in rows if r['host_handle'] == 'ucrgradsuccess')
        partner['is_locked'] = True
        tombstone, suppressed = group('rush')
        rows.append(suppressed)
        planned = plan(rows, [tombstone])
        self.assertEqual([], planned[0])
        database = Mock()
        database.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = []
        with patch.object(reconcile, '_reconciliation_rows', return_value=rows), \
             patch.object(reconcile, '_tombstoned_candidates', return_value=[tombstone]), \
             patch.object(reconcile, 'plan', return_value=planned), \
             patch.object(reconcile, 'same_event', side_effect=AssertionError('Do not rematch')), \
             patch.object(db, 'get_deleted_event_ids', return_value={tombstone['id']}), \
             patch.object(db, 'client', return_value=database):
            reconcile.main(notify=False)
        expected = [{'id': row['id'], 'replacement_id': None if row is suppressed else partner['id'],
                     'updated_at': row.get('updated_at')}
                    for row in sorted(rows, key=lambda r: r['id']) if row is not partner]
        database.rpc.assert_called_once_with('remap_assessed_event_sources', {'removals': expected})

    def test_precise_campus_winner_does_not_lose_time_or_remove_other_campus_rows(self):
        from test_duplicate_hosts import gala, celebration
        teaser = gala()
        timed = celebration(id='highlander_link_timed', source='campus_website')
        sibling = timed | {'id': 'ucr_events_timed'}
        updates, removed, replacements = plan([teaser, timed, sibling])
        self.assertEqual({teaser['id']}, removed)
        self.assertEqual({teaser['id']: sibling['id']}, replacements)
        self.assertTrue(all(r['starts_at'] == timed['starts_at'] for r in updates))

    def test_reconcile_scan_and_publication_share_import_identity(self):
        rows = [group('silent disglo')[0], group('rush')[0],
                {'id': 'manual_1', 'source': 'manual'},
                {'id': 'highlander_link_manual', 'source': 'manual'},
                {'id': 'ig_manual', 'source': 'manual'},
                {'id': 'highlander_link_wrong', 'source': 'instagram'},
                {'id': 'ig_wrong', 'source': 'campus_website'}]
        query = Mock()
        query.table.return_value = query.select.return_value = query.order.return_value = query.range.return_value = query
        query.execute.return_value.data = rows
        with patch.object(db, 'client', return_value=query):
            self.assertEqual([rows[1]], db.get_imported_events())
            self.assertEqual(rows[:2], _reconciliation_rows())


if __name__ == '__main__':
    unittest.main()
