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
                'rsvp_url':None, 'is_locked':False, **extra}

    def test_instagram_wins_and_retains_compatible_campus_metadata(self):
        campus = self.event('ucr_events_1', ends_at='2026-09-12T15:30:00-07:00', rsvp_url='https://example.org/register')
        ig = self.event('ig_arts_1')
        for rows in ([campus, ig], [ig, campus]):
            before = copy.deepcopy(rows)
            updates, deleted, replacements = reconcile.plan(rows)
            self.assertEqual({'ucr_events_1'}, deleted)
            self.assertEqual({'ucr_events_1': 'ig_arts_1'}, replacements)
            self.assertEqual(campus['ends_at'], updates[0]['ends_at'])
            self.assertEqual(campus['rsvp_url'], updates[0]['rsvp_url'])
            self.assertEqual(([], set(), {}), reconcile.plan(updates))
            self.assertEqual(before, rows)
            self.assertEqual(([], set(), {}), reconcile.plan([campus]))

    def test_cnas_room_description_matches_the_same_room(self):
        rows = [self.event('ucr_events_1', 'CNAS NEW FAMILY WELCOME', location='HUB (Highlander Union Building), 302', host='UCR Social'),
                self.event('ig_cnas_1', 'CNAS NEW FAMILY WELCOME', location='HUB 302', host='CNAS')]
        self.assertEqual({'ucr_events_1'}, reconcile.plan(rows)[1])

    def test_family_weekend_merges_variants_and_keeps_the_full_range(self):
        rows = [self.event('ucr_events_1', 'Save the Date: Highlander Family Weekend', starts_at='2026-11-06T00:00:00-08:00', location='UC Riverside')]
        for i, title in enumerate(['Highlander Family Weekend', 'Highlander Family Network Family Weekend', 'Highlander FAMILY WEEKEND']):
            rows.append(self.event(f'ig_club{i}_1', title, starts_at=rows[0]['starts_at'], location='UC Riverside', ends_at='2026-11-08T23:59:59-08:00'))
        updates, deleted, replacements = reconcile.plan(rows)
        self.assertEqual(3, len(deleted))
        self.assertEqual('2026-11-09T07:59:59+00:00', updates[0]['ends_at'])

    def test_shared_rsvp_confirms_physician_day_despite_title_variation(self):
        a = self.event('ucr_events_1', '4th Annual National Latino Physician Day Celebration', rsvp_url='https://ucr.qualtrics.com/jfe/form/ONE')
        b = self.event('ig_ppac_1', 'NATIONAL LATINO PHYSICIAN DAY', rsvp_url=a['rsvp_url']+'?utm_source=instagram', host='GradSuccess')
        self.assertEqual({'ucr_events_1'}, reconcile.plan([a,b])[1])

    def test_distinct_clubs_dates_places_and_registration_forms_stay_separate(self):
        cases = [
            [self.event('ig_a_1','General Meeting'), self.event('ig_b_1','General Meeting')],
            [self.event('ig_a_1','Fall Club General Meeting'), self.event('ig_b_1','Fall Club General Meeting')],
            [self.event('ig_a_1'), self.event('ucr_events_1', starts_at='2026-09-13T14:00:00-07:00')],
            [self.event('ig_a_1', location='Venue A',host='Club A'), self.event('ucr_events_1',location='Venue B',host='Club B')],
            [self.event('ig_a_1','General Meeting', rsvp_url='https://forms.example/signup?event=a'), self.event('ig_b_1','General Meeting', rsvp_url='https://forms.example/signup?event=b')],
            [self.event('ucr_events_1','Fall Involvement Fair'), self.event('manual_1','Fall Involvement Fair - SDU Appearance!')],
        ]
        for rows in cases:
            self.assertEqual(([], set(), {}), reconcile.plan(rows))

    def test_story_reshare_and_feed_row_of_one_post_reconcile(self):
        # September 19: both survived because the titles and hosts diverge.
        story = self.event('ig_post_3981794780021667232_20261022T1800Z',
                           'THE WELL\'S OPEN HOUSE "DOWN THE RABBIT HOLE: DISCOVER THE WELL"',
                           location='HUB 381', host='The Well',
                           source_url='https://www.instagram.com/stories/thewellucr/3983944040466618933/')
        feed = self.event('ig_thewellucr_20261022T1800Z', "The Well's Open House: Down the Rabbit Hole",
                          location='HUB 381', host='The Well at UCR', description='x' * 200,
                          source_url='https://www.instagram.com/p/DdCLUGHsjWg/')
        self.assertEqual(([], {story['id']}, {story['id']: feed['id']}), reconcile.plan([story, feed]))
        # The two parses of one post can disagree on room and end time.
        disputed = {**story, 'location': 'The Well', 'ends_at': '2026-10-22T19:00:00-07:00'}
        feed_ended = {**feed, 'ends_at': '2026-10-22T20:00:00-07:00'}
        self.assertEqual(([], {disputed['id']}, {disputed['id']: feed_ended['id']}),
                         reconcile.plan([disputed, feed_ended]))
        current = {**feed, 'id': 'ig_thewellucr_p3981794780021667232', 'source_url': None}
        self.assertEqual({story['id']}, reconcile.plan([story, current])[1])
        moved = {**feed, 'starts_at': '2026-10-23T11:00:00-07:00'}
        self.assertEqual(([], set(), {}), reconcile.plan([story, moved]))

    def test_room_code_spacing_and_host_account_match(self):
        a = self.event('ig_ucr_athletics_1', "Men's Basketball Tip-Off Banquet", location='LOFT 84',
                       host='UC Riverside Athletics', host_handle='ucr_athletics')
        b = self.event('ig_ucrmbb_1', 'UC Riverside Men’s Basketball Tip-Off Banquet', location='LOFT84',
                       host="UCR Men's Basketball", host_handle='ucrmbb')
        self.assertTrue(reconcile.same_event(a, b))
        c = self.event('ig_well_1', "The Well's Open House: Down the Rabbit Hole", location='',
                       host='The Well', host_handle='thewellucr')
        d = {**c, 'id': 'ig_wellstory_1', 'host': 'The Well at UCR'}
        self.assertTrue(reconcile.same_event(c, d))
        self.assertFalse(reconcile.same_event(c, {**d, 'host_handle': 'otherclub'}))

    def test_partner_promotion_tagging_the_organizer_reconciles(self):
        organizer = self.event('ig_aspb_ucr_1', 'Once Upon a Faire', location='Bell Tower & Pierce Lawns',
                               host='ASPB', host_handle='aspb_ucr', ends_at='2026-09-12T17:00:00-07:00',
                               description='Join us at Once Upon a Faire ' + 'x' * 200)
        partner = self.event('ig_rstageucr_1', 'Once Upon a Faire', location='UCR Campus',
                             host="R'Stage", host_handle='rstageucr', ends_at=organizer['ends_at'],
                             description="R’Stage has partnered with @aspb_ucr for Once Upon a Faire!")
        self.assertEqual({partner['id']}, reconcile.plan([organizer, partner])[1])
        untagged = {**partner, 'description': 'Once Upon a Faire'}
        early = {**partner, 'ends_at': '2026-09-12T15:00:00-07:00'}
        for other in (untagged, early):
            self.assertEqual(([], set(), {}), reconcile.plan([organizer, other]))

    def test_paraphrased_titles_alone_never_merge_accounts(self):
        # The CHASS story reposted the Alumni flyer, but its row carries no
        # evidence of that; the listing is resolved by review, not by title.
        alumni = self.event('ig_ucralumni_20261107T0800Z', 'UCR Homecoming featuring Funk Flex',
                            location='', host='UCR Alumni Association', host_handle='ucralumni')
        chass = self.event('ig_ucrchass_20261107T0800Z', 'Homecoming III featuring Funk Flex',
                           location='UCR', host='UCR CHASS', host_handle='ucrchass',
                           description='Homecoming III featuring Funk Flex')
        self.assertEqual(([], set(), {}), reconcile.plan([alumni, chass]))

    def test_lock_wins_and_deleted_group_cannot_reappear_via_another_source(self):
        campus, ig = self.event('ucr_events_1'), self.event('ig_a_1', is_locked=True)
        self.assertEqual(([], {'ucr_events_1'}, {'ucr_events_1': ig['id']}), reconcile.plan([campus,ig]))
        self.assertEqual(([], set(), {}), reconcile.plan([campus], [self.event('ig_old_1')]))
        self.assertEqual(([], set(), {}), reconcile.plan([ig], [campus]))

    def test_failed_canonical_write_never_deletes_duplicates(self):
        import db
        rows = [self.event('ucr_events_1',has_free_food=True), self.event('ig_a_1')]
        database = Mock()
        database.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.side_effect = RuntimeError('write failed')
        with patch.object(db,'get_event_rows',return_value=rows), \
             patch.object(db,'get_deleted_event_ids',return_value=set()), \
             patch.object(db,'client',return_value=database):
            with self.assertRaisesRegex(RuntimeError,'write failed'):
                reconcile.main(notify=False)
        database.table.return_value.update.assert_called_once_with({'has_free_food':True})
        database.rpc.assert_not_called()

    def test_concurrent_admin_change_stops_reconciliation_before_deletion(self):
        import db
        rows = [self.event('ucr_events_1',has_free_food=True), self.event('ig_a_1',updated_at=NOW)]
        database = Mock()
        query = database.table.return_value.update.return_value
        query.eq.return_value = query
        query.execute.return_value.data = []
        with patch.object(db,'get_event_rows',return_value=rows), \
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
                rows = [self.event('ucr_events_1', ends_at=ends_at, has_free_food=True),
                        self.event('ig_a_1', ends_at=ends_at)]
                updates, removed, replacements = reconcile.plan(rows, now=now)
                if eligible:
                    self.assertEqual(['ig_a_1'], [row['id'] for row in updates])
                    self.assertTrue(updates[0]['has_free_food'])
                    self.assertEqual({'ucr_events_1'}, removed)
                else:
                    self.assertEqual(([], set()), (updates, removed))

    def test_merging_an_already_notified_duplicate_preserves_alert_history(self):
        import db
        campus = self.event('ucr_events_1', 'Save the Date: Highlander Family Weekend')
        ig = self.event('ig_family_1', 'Highlander Family Weekend')
        database = Mock()
        database.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = [{
            'event_id':ig['id'], 'kind':'free_food', 'notified_at':'2026-09-01T12:00:00Z',
        }]
        with patch.object(db, 'client', return_value=database):
            reconcile._inherit_notifications([campus, ig], [], {ig['id']: campus['id']})
        aliases = database.table.return_value.upsert.call_args.args[0]
        self.assertEqual(campus['id'], aliases[0]['event_id'])
        self.assertEqual('2026-09-01T12:00:00Z', aliases[0]['notified_at'])
        self.assertTrue(database.table.return_value.upsert.call_args.kwargs['ignore_duplicates'])


if __name__ == '__main__':
    unittest.main()
