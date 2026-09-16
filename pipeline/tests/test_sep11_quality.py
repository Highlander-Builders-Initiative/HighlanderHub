"""Regressions from the September 11 run, using its saved source text."""
import copy
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import reconcile_events as reconcile

NOW = "2026-09-11T17:03:50+00:00"


class CrossSourceReconciliationTests(unittest.TestCase):
    def setUp(self):
        # Keep main()'s age filter from expiring these fixed historical fixtures.
        clock = patch.object(reconcile, 'datetime', wraps=datetime)
        clock.start().now.return_value = datetime.fromisoformat(NOW)
        self.addCleanup(clock.stop)

    def event(self, eid, title='The Great Picture: Making and Showing the Largest Print Photograph', **extra):
        return {'id':eid, 'title':title, 'starts_at':'2026-09-12T14:00:00-07:00',
                'ends_at':None, 'source':'instagram' if eid.startswith('ig_') else 'campus_website',
                'location':'UCR ARTS', 'host':'UCR Arts', 'has_free_food':False,
                'is_free':True, 'rsvp_url':None, 'is_locked':False, **extra}

    def test_campus_metadata_wins_and_rerun_is_idempotent(self):
        campus = self.event('campus_1', ends_at='2026-09-12T15:30:00-07:00', rsvp_url='https://example.org/register')
        ig = self.event('ig_arts_1', is_free=False)
        for rows in ([campus, ig], [ig, campus]):
            before = copy.deepcopy(rows)
            updates, deleted = reconcile.plan(rows)
            self.assertEqual({'ig_arts_1'}, deleted)
            self.assertEqual([], updates)
            self.assertEqual(before, rows)
            self.assertEqual(([], set()), reconcile.plan([campus]))

    def test_cnas_room_description_matches_the_same_room(self):
        rows = [self.event('campus_1', 'CNAS NEW FAMILY WELCOME', location='HUB (Highlander Union Building), 302', host='UCR Social'),
                self.event('ig_cnas_1', 'CNAS NEW FAMILY WELCOME', location='HUB 302', host='CNAS')]
        self.assertEqual({'ig_cnas_1'}, reconcile.plan(rows)[1])

    def test_family_weekend_merges_variants_and_keeps_the_full_range(self):
        rows = [self.event('campus_1', 'Save the Date: Highlander Family Weekend', starts_at='2026-11-06T00:00:00-08:00', location='UC Riverside')]
        for i, title in enumerate(['Highlander Family Weekend', 'Highlander Family Network Family Weekend', 'Highlander FAMILY WEEKEND']):
            rows.append(self.event(f'ig_club{i}_1', title, starts_at=rows[0]['starts_at'], location='UC Riverside', ends_at='2026-11-08T23:59:59-08:00'))
        updates, deleted = reconcile.plan(rows)
        self.assertEqual(3, len(deleted))
        self.assertEqual('2026-11-09T07:59:59+00:00', updates[0]['ends_at'])

    def test_shared_rsvp_confirms_physician_day_despite_title_variation(self):
        a = self.event('campus_1', '4th Annual National Latino Physician Day Celebration', rsvp_url='https://ucr.qualtrics.com/jfe/form/ONE', is_free=True)
        b = self.event('ig_ppac_1', 'NATIONAL LATINO PHYSICIAN DAY', rsvp_url=a['rsvp_url']+'?utm_source=instagram', host='GradSuccess', is_free=False)
        self.assertEqual({'ig_ppac_1'}, reconcile.plan([a,b])[1])

    def test_distinct_clubs_dates_places_and_registration_forms_stay_separate(self):
        cases = [
            [self.event('ig_a_1','General Meeting'), self.event('ig_b_1','General Meeting')],
            [self.event('ig_a_1','Fall Club General Meeting'), self.event('ig_b_1','Fall Club General Meeting')],
            [self.event('ig_a_1'), self.event('campus_1', starts_at='2026-09-13T14:00:00-07:00')],
            [self.event('ig_a_1', location='Venue A',host='Club A'), self.event('campus_1',location='Venue B',host='Club B')],
            [self.event('ig_a_1','General Meeting', rsvp_url='https://forms.example/signup?event=a'), self.event('ig_b_1','General Meeting', rsvp_url='https://forms.example/signup?event=b')],
            [self.event('campus_1','Fall Involvement Fair'), self.event('manual_1','Fall Involvement Fair - SDU Appearance!')],
        ]
        for rows in cases:
            self.assertEqual(([],set()), reconcile.plan(rows))

    def test_lock_wins_and_deleted_group_cannot_reappear_via_another_source(self):
        campus, ig = self.event('campus_1'), self.event('ig_a_1', is_locked=True, is_free=False)
        self.assertEqual(([],{'campus_1'}), reconcile.plan([campus,ig]))
        self.assertEqual(([],{'campus_1'}), reconcile.plan([campus], [self.event('ig_old_1')]))
        self.assertEqual(([],set()), reconcile.plan([ig], [campus]))

    def test_failed_canonical_write_never_deletes_duplicates(self):
        import db
        rows = [self.event('campus_1'), self.event('ig_a_1',has_free_food=True)]
        database = Mock()
        database.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.side_effect = RuntimeError('write failed')
        with patch.object(db,'get_imported_events',return_value=rows), \
             patch.object(db,'get_deleted_event_ids',return_value=set()), \
             patch.object(db,'client',return_value=database):
            with self.assertRaisesRegex(RuntimeError,'write failed'):
                reconcile.main(notify=False)
        database.table.return_value.update.assert_called_once_with({'has_free_food':True})
        database.rpc.assert_not_called()

    def test_concurrent_admin_change_stops_reconciliation_before_deletion(self):
        import db
        rows = [self.event('campus_1',updated_at=NOW), self.event('ig_a_1',has_free_food=True)]
        database = Mock()
        query = database.table.return_value.update.return_value
        query.eq.return_value = query
        query.execute.return_value.data = []
        with patch.object(db,'get_imported_events',return_value=rows), \
             patch.object(db,'get_deleted_event_ids',return_value=set()), \
             patch.object(db,'client',return_value=database):
            with self.assertRaisesRegex(RuntimeError,'changed during reconciliation'):
                reconcile.main(notify=False)
        database.table.return_value.update.assert_called_once_with({'has_free_food':True})
        query.eq.assert_any_call('is_locked', False)
        query.eq.assert_any_call('updated_at', NOW)
        database.rpc.assert_not_called()

    def test_finished_duplicates_are_skipped_but_ongoing_events_reconcile(self):
        now = datetime.fromisoformat('2026-09-13T00:00:00+00:00')
        for ends_at, eligible in ((None, False),
                                  ('2026-09-12T23:00:00+00:00', False),
                                  ('2026-09-13T01:00:00+00:00', True)):
            with self.subTest(ends_at=ends_at):
                rows = [self.event('campus_1', ends_at=ends_at),
                        self.event('ig_a_1', ends_at=ends_at, has_free_food=True)]
                updates, removed = reconcile.plan(rows, now=now)
                if eligible:
                    self.assertEqual(['campus_1'], [row['id'] for row in updates])
                    self.assertTrue(updates[0]['has_free_food'])
                    self.assertEqual({'ig_a_1'}, removed)
                else:
                    self.assertEqual(([], set()), (updates, removed))

    def test_merging_an_already_notified_duplicate_preserves_alert_history(self):
        import db
        campus = self.event('campus_1', 'Save the Date: Highlander Family Weekend')
        ig = self.event('ig_family_1', 'Highlander Family Weekend')
        database = Mock()
        database.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = [{
            'event_id':ig['id'], 'kind':'free_food', 'notified_at':'2026-09-01T12:00:00Z',
        }]
        with patch.object(db, 'client', return_value=database):
            reconcile._inherit_notifications([campus, ig], [], {ig['id']})
        aliases = database.table.return_value.upsert.call_args.args[0]
        self.assertEqual(campus['id'], aliases[0]['event_id'])
        self.assertEqual('2026-09-01T12:00:00Z', aliases[0]['notified_at'])
        self.assertTrue(database.table.return_value.upsert.call_args.kwargs['ignore_duplicates'])


if __name__ == '__main__':
    unittest.main()
