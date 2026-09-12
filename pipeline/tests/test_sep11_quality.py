"""Regressions from the September 11 run, using its saved source text."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extract_stories as extract
import reconcile_events as reconcile
from classify import classify_content_kind, detect_free_food
from story_dates import align_printed_dates, evidence_dates

NOW = "2026-09-11T17:03:50+00:00"


class September11QualityTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = json.loads((Path(__file__).parent / 'fixtures/sep11_quality_stories.json').read_text())

    def row(self, sid):
        f = self.fixtures[sid]
        return extract._to_event_row(f['raw'], f['cached'], {}, NOW)

    def test_single_time_flyer_corrects_the_wrong_day_and_retires_old_id(self):
        row, retired = self.row('3983589040137507600')
        self.assertEqual('2026-09-16T01:30:00+00:00', row['starts_at'])
        self.assertIn('ig_post_3983413828485231669_20260924T0130Z', retired)

    def test_labeled_date_tiles_recover_homecoming(self):
        row, retired = self.row('3983470688672731198')
        self.assertEqual('2026-11-07T08:00:00+00:00', row['starts_at'])
        self.assertEqual('2026-11-08T07:59:59+00:00', row['ends_at'])
        self.assertIn('ig_post_3983454610698999617_20260726T0700Z', retired)

    def test_dotted_halloween_date_has_corroboration_but_prices_do_not(self):
        row, _ = self.row('3983345563378243344')
        self.assertEqual('2026-11-01T04:00:00+00:00', row['starts_at'])
        self.assertEqual('2026-11-01T10:00:00+00:00', row['ends_at'])
        for text in ('Room 10.31 at 5 PM', '$10.31 at 5 PM', 'Price 10.31 at 5 PM', 'Workshop 10.31', 'EKG reading 5.62 at 5 PM'):
            self.assertEqual(set(), evidence_dates(text), text)
        # The ticket's small start clock was visually reviewed as 9:11 PM;
        # a corrected OCR cache must override the model's rounded 9 PM.
        f = self.fixtures['3983345563378243344']
        f['cached']['ocr_text'] = f['cached']['ocr_text'].replace('PJIPM-2AM', '9:11PM-2AM')
        row, _ = self.row('3983345563378243344')
        self.assertEqual('2026-11-01T04:11:00+00:00', row['starts_at'])
        self.assertEqual('2026-11-01T10:00:00+00:00', row['ends_at'])

    def test_explicit_year_and_dst_are_respected_when_correcting_dates(self):
        raw = {'posted_at':'2026-09-11T16:00:00Z'}
        for text, expected in (
            ('Workshop 11/07/26', '2026-11-07T23:00:00+00:00'),
            ('Workshop November 7, 2027', '2027-11-07T23:00:00+00:00'),
            ('Workshop 2026-11-07', '2026-11-07T23:00:00+00:00'),
        ):
            self.assertEqual((expected, None), align_printed_dates(raw, {'ocr_text':text}, '2026-09-15T15:00:00-07:00', None))

    def test_multidate_flyer_cannot_publish_an_unprinted_day(self):
        self.assertIsNone(align_printed_dates(
            {'posted_at': NOW}, {'ocr_text': 'Workshops September 15 and September 22'},
            '2026-09-23T18:30:00-07:00', None,
        ))

    def test_explicit_timezone_preserves_the_previous_pacific_day(self):
        start, end = '2026-09-15T05:00:00+00:00', '2026-09-15T06:00:00+00:00'
        self.assertEqual((start, end), align_printed_dates(
            {'posted_at': NOW}, {'ocr_text':'Workshop September 15, 1 AM-2 AM ET'}, start, end,
        ))

    def test_family_weekend_includes_the_entire_last_day(self):
        for sid in ('3981812676561360917', '3983911763883588438'):
            row, _ = self.row(sid)
            self.assertEqual('2026-11-06T08:00:00+00:00', row['starts_at'])
            self.assertEqual('2026-11-09T07:59:59+00:00', row['ends_at'])

    def test_resource_posts_are_skipped_and_the_published_id_is_retired(self):
        row, retired = self.row('3983302762182864922')
        self.assertIsNone(row)
        self.assertIn('ig_post_3983267399491784784_20260910T1858Z', retired)
        row, retired = self.row('3983965996258496964')
        self.assertIsNone(row)
        self.assertIn('ig_ucr_caps_20260906T0700Z', retired)

    def test_awareness_workshops_remain_events_but_service_closures_do_not(self):
        self.assertEqual('other', classify_content_kind('localist', title='SRC Closures & Modified Hours', audiences=['Students']))
        self.assertEqual('student_event', classify_content_kind('instagram', title='Suicide Prevention Week Workshop', description='Resources and support. September 15 at 5 PM.'))
        self.assertEqual('student_event', classify_content_kind('instagram', title='Mental Health Awareness Week', ocr_text='Join our workshop September 15 at 5 PM for resources.'))

    def test_free_kona_ice_is_food_but_ice_sales_and_merch_are_not(self):
        self.assertTrue(detect_free_food('UCRBG Student Welcome Week- Free Kona Ice (first 100 students)'))
        for text in ('Free ice skating', 'Free merchandise', 'Kona Ice for sale'):
            self.assertFalse(detect_free_food(text))

    def test_original_author_supplies_host_and_anonymization_still_applies(self):
        f = self.fixtures['3983424892589486822']
        row, _ = extract._to_event_row(f['raw'], f['cached'], {'label':'GradSuccess'}, NOW, {'ppacatucr':{'label':'Health Professions Advising'}})
        self.assertEqual('ppacatucr', row['host_handle'])
        self.assertEqual('Health Professions Advising', row['host'])
        raw = {**f['raw'], 'handle':'highlander_opps'}
        row, _ = extract._to_event_row(raw, f['cached'], {}, NOW)
        self.assertIsNone(row['host_handle'])
        self.assertEqual('', row['host'])

    def test_error_results_are_saved_and_retried_not_terminal_hits(self):
        raw = {'id':'retry', 'handle':'club', 'image_url':'https://example.org/flyer.jpg'}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(extract, 'EXTRACTED_DIR', Path(directory)), \
             patch.object(extract, '_load_remote_cache', return_value=None), \
             patch.object(extract, '_write_remote_cache') as remote, \
             patch.object(extract, '_download_image', return_value=b'flyer'), \
             patch.object(extract, '_vision_ocr', side_effect=[RuntimeError('service unavailable'), '']) as ocr:
            result = extract._process_story(raw, {})
            self.assertEqual('ocr', result['result']['stage'])
            self.assertIn('service unavailable', json.loads((Path(directory)/'retry.json').read_text())['result']['error'])
            remote.assert_called_with(result)
            self.assertEqual('no_text', extract._process_story(raw, {})['status'])
            self.assertEqual(2, ocr.call_count)

    def test_partial_failure_saves_successes_then_fails_stage_without_sending(self):
        f = self.fixtures['3983589040137507600']
        with patch.object(extract, 'ensure_dirs'), \
             patch.object(extract, '_load_account_meta', return_value={'tpusa_at_ucr':{}}), \
             patch.object(extract, '_iter_raw_stories', return_value=[f['raw'], {'id':'failed'}]), \
             patch.object(extract, '_process_story', side_effect=[f['cached'], {'status':'error'}]), \
             patch('assessed_events.publish_stories', side_effect=RuntimeError('1 source assessment(s) failed')) as publish, \
             patch.object(extract, 'notify_free_food_events') as notify:
            with self.assertRaisesRegex(RuntimeError, '1 source assessment.*failed'):
                extract.main(notify=False)
            self.assertEqual(2, len(publish.call_args.args[0]))
            self.assertFalse(publish.call_args.kwargs['notify'])
            notify.assert_not_called()


class CrossSourceReconciliationTests(unittest.TestCase):
    def event(self, eid, title='The Great Picture: Making and Showing the Largest Print Photograph', **extra):
        return {'id':eid, 'title':title, 'starts_at':'2026-09-12T14:00:00-07:00',
                'ends_at':None, 'source':'instagram' if eid.startswith('ig_') else 'campus_website',
                'location':'UCR ARTS', 'host':'UCR Arts', 'has_free_food':False,
                'is_free':True, 'rsvp_url':None, 'is_locked':False, **extra}

    def test_campus_metadata_wins_and_rerun_is_idempotent(self):
        campus = self.event('ucr_events_1', ends_at='2026-09-12T15:30:00-07:00', rsvp_url='https://example.org/register')
        ig = self.event('ig_arts_1', is_free=False)
        for rows in ([campus, ig], [ig, campus]):
            before = copy.deepcopy(rows)
            updates, deleted = reconcile.plan(rows)
            self.assertEqual({'ig_arts_1'}, deleted)
            self.assertEqual([], updates)
            self.assertEqual(before, rows)
            self.assertEqual(([], set()), reconcile.plan([campus]))

    def test_cnas_room_description_matches_the_same_room(self):
        rows = [self.event('ucr_events_1', 'CNAS NEW FAMILY WELCOME', location='HUB (Highlander Union Building), 302', host='UCR Social'),
                self.event('ig_cnas_1', 'CNAS NEW FAMILY WELCOME', location='HUB 302', host='CNAS')]
        self.assertEqual({'ig_cnas_1'}, reconcile.plan(rows)[1])

    def test_family_weekend_merges_variants_and_keeps_the_full_range(self):
        rows = [self.event('ucr_events_1', 'Save the Date: Highlander Family Weekend', starts_at='2026-11-06T00:00:00-08:00', location='UC Riverside')]
        for i, title in enumerate(['Highlander Family Weekend', 'Highlander Family Network Family Weekend', 'Highlander FAMILY WEEKEND']):
            rows.append(self.event(f'ig_club{i}_1', title, starts_at=rows[0]['starts_at'], location='UC Riverside', ends_at='2026-11-08T23:59:59-08:00'))
        updates, deleted = reconcile.plan(rows)
        self.assertEqual(3, len(deleted))
        self.assertEqual('2026-11-09T07:59:59+00:00', updates[0]['ends_at'])

    def test_shared_rsvp_confirms_physician_day_despite_title_variation(self):
        a = self.event('ucr_events_1', '4th Annual National Latino Physician Day Celebration', rsvp_url='https://ucr.qualtrics.com/jfe/form/ONE', is_free=True)
        b = self.event('ig_ppac_1', 'NATIONAL LATINO PHYSICIAN DAY', rsvp_url=a['rsvp_url']+'?utm_source=instagram', host='GradSuccess', is_free=False)
        self.assertEqual({'ig_ppac_1'}, reconcile.plan([a,b])[1])

    def test_distinct_clubs_dates_places_and_registration_forms_stay_separate(self):
        cases = [
            [self.event('ig_a_1','General Meeting'), self.event('ig_b_1','General Meeting')],
            [self.event('ig_a_1','Fall Club General Meeting'), self.event('ig_b_1','Fall Club General Meeting')],
            [self.event('ig_a_1'), self.event('ucr_events_1', starts_at='2026-09-13T14:00:00-07:00')],
            [self.event('ig_a_1', location='Venue A',host='Club A'), self.event('ucr_events_1',location='Venue B',host='Club B')],
            [self.event('ig_a_1','General Meeting', rsvp_url='https://forms.example/signup?event=a'), self.event('ig_b_1','General Meeting', rsvp_url='https://forms.example/signup?event=b')],
            [self.event('ucr_events_1','Fall Involvement Fair'), self.event('highlander_link_1','Fall Involvement Fair - SDU Appearance!')],
        ]
        for rows in cases:
            self.assertEqual(([],set()), reconcile.plan(rows))

    def test_lock_wins_and_deleted_group_cannot_reappear_via_another_source(self):
        campus, ig = self.event('ucr_events_1'), self.event('ig_a_1', is_locked=True, is_free=False)
        self.assertEqual(([],{'ucr_events_1'}), reconcile.plan([campus,ig]))
        self.assertEqual(([],{'ucr_events_1'}), reconcile.plan([campus], [self.event('ig_old_1')]))
        self.assertEqual(([],set()), reconcile.plan([ig], [campus]))

    def test_failed_canonical_write_never_deletes_duplicates(self):
        import db
        rows = [self.event('ucr_events_1'), self.event('ig_a_1',has_free_food=True)]
        database = Mock()
        database.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.side_effect = RuntimeError('write failed')
        with patch.object(db,'get_imported_events',return_value=rows), \
             patch.object(db,'get_deleted_event_ids',return_value=set()), \
             patch.object(db,'client',return_value=database), \
             patch.object(db,'delete_unlocked_event_rows_by_ids') as delete:
            with self.assertRaisesRegex(RuntimeError,'write failed'):
                reconcile.main(notify=False)
            delete.assert_not_called()

    def test_concurrent_admin_change_stops_reconciliation_before_deletion(self):
        import db
        rows = [self.event('ucr_events_1',updated_at=NOW), self.event('ig_a_1',has_free_food=True)]
        database = Mock()
        query = database.table.return_value.update.return_value
        query.eq.return_value = query
        query.execute.return_value.data = []
        with patch.object(db,'get_imported_events',return_value=rows), \
             patch.object(db,'get_deleted_event_ids',return_value=set()), \
             patch.object(db,'client',return_value=database), \
             patch.object(db,'delete_unlocked_event_rows_by_ids') as delete:
            with self.assertRaisesRegex(RuntimeError,'changed during reconciliation'):
                reconcile.main(notify=False)
        database.table.return_value.update.assert_called_once_with({'has_free_food':True})
        query.eq.assert_any_call('is_locked', False)
        query.eq.assert_any_call('updated_at', NOW)
        delete.assert_not_called()

    def test_merging_an_already_notified_duplicate_preserves_alert_history(self):
        import db
        campus = self.event('ucr_events_1', 'Save the Date: Highlander Family Weekend')
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
