"""hpix migration: billing boundaries, failures, details and paid-run recovery."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import apify_posts as apify
from hpix_contract import completed_profiles

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)
ACCOUNTS = {'club': {'handle': 'club', 'instagram_user_id': 42},
            'quiet': {'handle': 'quiet', 'instagram_user_id': 43}}
STATE = {h: {'activated_at': '2026-09-01T00:00:00Z',
             'scanned_through': '2026-09-19T00:00:00Z'} for h in ACCOUNTS}


def row(handle='club', owner='club', owner_id='42'):
    return {'kind': 'post', 'input': handle, 'data': {
        '__typename': 'GraphImage', 'id': '123', 'shortcode': 'ABC',
        'taken_at_timestamp': 1789776000, 'owner': {'username': owner, 'id': owner_id},
        'coauthor_producers': [], 'edge_media_to_caption': {'edges': [{'node': {'text': 'Event'}}]},
        'display_resources': [{'src': 'https://example.com/photo.jpg', 'config_width': 1080, 'config_height': 1080}],
        'is_video': False}}


def run(**updates):
    return {'id': 'feed-run', 'actId': apify.HPIX_ACTOR_ID, 'status': 'SUCCEEDED',
            'defaultDatasetId': 'feed-data', 'options': {'maxTotalChargeUsd': .8},
            'chargedEventCounts': {'post_scraped': 1, 'apify-actor-start': 1},
            'pricingInfo': {'pricingPerEvent': {'actorChargeEvents': {
                key: {'eventPriceUsd': price} for key, price in {
                    'post_scraped': .00099, 'individual_post_scraped': .00149,
                    'profile_scraped': .00299, 'restricted_post_scraped': .1,
                    'apify-actor-start': .00005}.items()}}}, **updates}


class HpixCollectionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'run.json'
        self.path.write_text(json.dumps({'id': 'feed-run', 'actor_id': apify.HPIX_ACTOR_ID,
            'posts_per_profile': 100, 'started_at': NOW.isoformat(),
            'newer_than': '2026-09-18T23:54:59Z', 'consumed': False}))
        self.api = Mock(run_file=self.path)
        self.api.run.return_value = run()
        self.api.run_log.return_value = '\n'.join(f'INFO  Crawler: [{h}] Finished scraping posts' for h in ACCOUNTS)
        self.api.items.return_value = [row()]
        self.known = self.enterContext(patch("post_archive._mirrored_media_ids", return_value=set()))
        self.enterContext(patch.object(apify, 'POST_BACKFILL_SINCE', ''))
        self.mirror = self.enterContext(patch.object(apify, 'mirror'))
        self.write = self.enterContext(patch.object(apify, 'write_post'))
        self.upsert = self.enterContext(patch('db.upsert_batched'))

    def collect(self):
        apify.collect(self.api, ACCOUNTS, copy.deepcopy(STATE), NOW,
                      limit=100, max_charge=1, timeout=300, archive=apify.ArchiveIndex())

    def status(self, handle):
        return next(r for r in self.upsert.call_args.args[1] if r['handle'] == handle)

    def detail(self, **updates):
        data = {'id': '123_77', 'pk': '123', 'code': 'ABC', 'taken_at': 1789776000,
                'user': {'username': 'partner', 'pk': '77'}, 'media_type': 1,
                'coauthor_producers': [{'username': 'club', 'pk': '42'}],
                'caption': {'text': 'Event'}, 'image_versions2': {'candidates': [
                    {'url': 'https://example.com/photo.jpg', 'width': 1080, 'height': 1080}]}, **updates}
        self.api.details.return_value = (run(id='detail-run', options={'maxTotalChargeUsd': .2}),
                                          [{'kind': 'post', 'data': data}])

    def test_normal_and_explicit_quiet_checks_advance_without_enrichment(self):
        self.collect()
        self.assertEqual('ok', self.status('club')['last_status'])
        self.assertEqual('ok', self.status('quiet')['last_status'])
        self.api.details.assert_not_called()
        self.assertEqual('123', self.write.call_args.args[0]['media_id'])

    def test_null_profile_overrides_finish_without_poisoning_healthy_club(self):
        self.api.items.return_value = [row(), {'kind': 'profile', 'input': 'quiet', 'data': None}]
        with self.assertRaises(apify.PartialCollection): self.collect()
        self.assertEqual('ok', self.status('club')['last_status'])
        self.assertEqual(STATE['quiet']['scanned_through'], self.status('quiet')['scanned_through'])
        self.assertIsNone(json.loads(self.path.read_text())['halt_reason'])

    def test_all_null_profiles_are_failure_not_systemic_schema_halt(self):
        self.api.items.return_value = [{'kind': 'profile', 'input': h, 'error': 'Account not found'} for h in ACCOUNTS]
        with self.assertRaises(apify.PartialCollection): self.collect()
        self.assertIsNone(json.loads(self.path.read_text())['halt_reason'])
        self.assertTrue(all(self.status(h)['last_status'] == 'incomplete' for h in ACCOUNTS))

    def test_media_error_retains_only_its_profile_without_systemic_halt(self):
        for kind, source in [('post', 'https://www.instagram.com/club/posts'),
                             ('reel', 'https://instagram.com/CLUB/reels/'),
                             ('post', 'club'), ('profile', 'https://www.instagram.com/club/')]:
            with self.subTest(kind=kind, source=source):
                self.api.items.return_value = [{'kind': kind, 'input': source,
                                               'error': 'Deleted or restricted post'}]
                with self.assertRaises(apify.PartialCollection) as raised:
                    self.collect()
                self.assertNotIsInstance(raised.exception, apify.CollectionHalted)
                self.assertEqual(STATE['club']['scanned_through'], self.status('club')['scanned_through'])
                self.assertEqual('incomplete', self.status('club')['last_status'])
                self.assertEqual('ok', self.status('quiet')['last_status'])
                saved = json.loads(self.path.read_text())
                self.assertEqual(0, saved['invalid'])
                self.assertIsNone(saved['halt_reason'])
                self.assertIn('club: Deleted or restricted post', saved['errors'])
        self.api.details.assert_not_called()
        self.write.assert_not_called()

    def test_unattributable_error_still_halts(self):
        for source in [None, 'https://example.com/club/posts',
                       'https://www.instagram.com/stranger/posts',
                       'https://www.instagram.com/p/ABC/']:
            with self.subTest(source=source):
                self.api.items.return_value = [{'kind': 'post', 'input': source,
                                               'error': 'Deleted or restricted post'}]
                with self.assertRaises(apify.CollectionHalted): self.collect()
                self.assertEqual(1, json.loads(self.path.read_text())['invalid'])

    def test_deleted_post_row_from_report_does_not_poison_quiet_profile(self):
        accounts = {'deltagamma_ucr': {'handle': 'deltagamma_ucr'}, 'quiet': ACCOUNTS['quiet']}
        state = {h: copy.deepcopy(STATE['club']) for h in accounts}
        self.api.items.return_value = [{'kind': 'post',
            'input': 'https://www.instagram.com/deltagamma_ucr/posts',
            'error': 'Deleted or restricted post'}]
        self.api.run_log.return_value = '\n'.join(
            f'INFO  Crawler: [{h}] Finished scraping posts' for h in accounts)
        with self.assertRaises(apify.PartialCollection) as raised:
            apify.collect(self.api, accounts, state, NOW, limit=100, max_charge=1, timeout=300, archive=apify.ArchiveIndex())
        self.assertNotIsInstance(raised.exception, apify.CollectionHalted)
        self.assertEqual('incomplete', self.status('deltagamma_ucr')['last_status'])
        self.assertEqual('ok', self.status('quiet')['last_status'])
        self.assertIsNone(json.loads(self.path.read_text())['halt_reason'])

    def test_media_error_does_not_mask_malformed_output(self):
        self.api.items.return_value = [
            {'kind': 'post', 'input': 'https://www.instagram.com/club/posts',
             'error': 'Deleted or restricted post'},
            {'kind': 'post', 'input': 'quiet', 'data': {}}]
        with self.assertRaises(apify.CollectionHalted): self.collect()
        self.assertEqual(1, json.loads(self.path.read_text())['invalid'])

    def test_empty_dataset_without_completion_advances_nothing(self):
        self.api.items.return_value = []; self.api.run_log.return_value = 'Finished crawler'
        with self.assertRaises(apify.PartialCollection): self.collect()
        self.assertEqual('incomplete', self.status('quiet')['last_status'])

    def test_collaboration_details_once_for_repeated_shortcode(self):
        self.api.items.return_value = [row(owner='partner', owner_id='77')] * 2
        self.detail(); self.collect()
        self.api.details.assert_called_once()
        self.assertEqual(['ABC'], self.api.details.call_args.args[0])
        self.assertEqual(.2, self.api.details.call_args.kwargs['max_charge'])
        self.write.assert_called_once()
        self.assertEqual('club', self.write.call_args.args[0]['handle'])
        self.assertEqual('partner', self.write.call_args.args[0]['owner_username'])

    def test_tail_batch_defers_then_reuses_paid_feed_for_details(self):
        self.path.unlink()
        clock = [0]
        api = apify.ApifyClient('test', self.path)
        def request(method, *args, **kwargs):
            if method == 'POST':
                clock[0] += 40
            return {'data': run(startedAt=NOW.isoformat())}
        api.request = Mock(side_effect=request)
        api.items = Mock(return_value=[row(owner='partner', owner_id='77')])
        api.run_log = self.api.run_log
        self.detail()
        api.details = self.api.details
        job = {'mode': 'discovery', 'handles': list(ACCOUNTS),
               'file': str(self.path), 'limit': 100, 'max_charge': 1,
               'cutoff': '2026-09-18T23:54:59Z', 'done': False}
        plan = {'jobs': [job], 'complete': False}
        plan_path = self.path.with_name('plan.json')
        with patch.object(apify, 'PLAN_FILE', plan_path), \
             patch.object(apify, 'ApifyClient', return_value=api), \
             patch.object(apify.time, 'monotonic', side_effect=lambda: clock[0]):
            with self.assertRaisesRegex(apify.PartialCollection, 'detail enrichment'):
                apify.execute_plan('test', ACCOUNTS, STATE, NOW, plan, 80, archive=apify.ArchiveIndex())
            self.assertFalse(json.loads(self.path.read_text())['consumed'])
            self.assertFalse(json.loads(plan_path.read_text())['jobs'][0]['done'])
            self.assertFalse(plan['complete'])
            api.details.assert_not_called()
            self.upsert.assert_not_called()
            self.mirror.assert_not_called()
            self.write.assert_not_called()

            apify.execute_plan('test', ACCOUNTS, STATE, NOW, plan, 300, archive=apify.ArchiveIndex())

        self.assertEqual(['POST', 'GET'], [c.args[0] for c in api.request.call_args_list])
        self.assertTrue(plan['complete'])
        self.assertTrue(json.loads(self.path.read_text())['consumed'])
        api.details.assert_called_once()
        self.assertEqual('ok', self.status('club')['last_status'])
        self.assertEqual('partner', self.write.call_args.args[0]['owner_username'])

    def test_known_collaboration_is_not_enriched_or_overwritten(self):
        self.known.return_value = {'123'}
        self.api.items.return_value = [row(owner='partner', owner_id='77')]
        self.collect(); self.api.details.assert_not_called(); self.write.assert_not_called()

    def test_individual_reel_details_are_accepted(self):
        self.api.items.return_value = [row(owner='partner', owner_id='77')]
        self.detail(media_type=2)
        self.api.details.return_value[1][0]['kind'] = 'reel'
        self.collect()
        self.assertEqual('GraphVideo', self.write.call_args.args[0]['typename'])

    def test_verified_unrelated_repost_does_not_strand_a_matching_feed(self):
        owned = row(); owned['data'].update(id='456', shortcode='DEF')
        self.api.items.return_value = [row(owner='partner', owner_id='77'), owned]
        self.detail(coauthor_producers=[])
        self.collect()
        self.write.assert_called_once()
        self.assertEqual('456', self.write.call_args.args[0]['media_id'])
        self.assertEqual('ok', self.status('club')['last_status'])

    def test_verified_repost_only_feed_advances_and_excludes_repost_next_cycle(self):
        repost = row(owner='partner', owner_id='77')
        self.api.items.return_value = [repost]
        self.detail(coauthor_producers=[])
        self.collect()
        self.assertEqual('ok', self.status('club')['last_status'])
        self.assertEqual(NOW.isoformat(), self.status('club')['scanned_through'])
        self.assertEqual([], json.loads(self.path.read_text())['errors'])
        self.api.details.assert_called_once()

        state = {r['handle']: r for r in self.upsert.call_args.args[1]}
        later = NOW.replace(hour=8)
        self.path.write_text(json.dumps({'id': 'next-feed', 'actor_id': apify.HPIX_ACTOR_ID,
            'posts_per_profile': 100, 'started_at': later.isoformat(), 'consumed': False}))
        def filtered_items(_):
            cutoff = apify.parse_instant(self.api.run.call_args.args[0]['onlyPostsNewerThan'])
            self.assertGreater(cutoff.timestamp(), repost['data']['taken_at_timestamp'])
            return []
        self.api.items.side_effect = filtered_items
        apify.collect(self.api, ACCOUNTS, state, later, limit=100, max_charge=1, timeout=300, archive=apify.ArchiveIndex())
        self.assertEqual(later.isoformat(), self.status('club')['scanned_through'])
        self.api.details.assert_called_once()
        self.mirror.assert_not_called()
        self.write.assert_not_called()

    def test_verified_repost_requires_completion_and_uncapped_run(self):
        for log in ['Finished crawler', 'INFO  Crawler: [club] Scraped 100/100 posts\n'
                    'INFO  Crawler: [club] Finished scraping posts']:
            with self.subTest(log=log):
                self.api.items.return_value = [row(owner='partner', owner_id='77')]
                self.api.run_log.return_value = log
                self.detail(coauthor_producers=[])
                with self.assertRaises(apify.PartialCollection): self.collect()
                self.assertEqual(STATE['club']['scanned_through'], self.status('club')['scanned_through'])
                self.write.assert_not_called()

    def test_verified_repost_counts_as_valid_output_alongside_malformed_row(self):
        self.api.items.return_value = [row(owner='partner', owner_id='77'),
                                      {'kind': 'post', 'input': 'quiet', 'data': {}}]
        self.detail(coauthor_producers=[])
        with self.assertRaises(apify.PartialCollection) as raised: self.collect()
        self.assertNotIsInstance(raised.exception, apify.CollectionHalted)
        self.assertEqual('ok', self.status('club')['last_status'])
        self.assertEqual('incomplete', self.status('quiet')['last_status'])
        self.assertEqual(1, json.loads(self.path.read_text())['invalid'])
        self.write.assert_not_called()

    def test_wrong_detail_identity_and_unaccepted_collaboration_retain_checkpoint(self):
        for changes in ({'id': '999_77'}, {'code': 'OTHER'},
                        {'coauthor_producers': [], 'image_versions2': {'candidates': []}},
                        {'coauthor_producers': [{'username': 'club', 'pk': '999'}]}):
            with self.subTest(changes=changes):
                self.api.items.return_value = [row(owner='partner', owner_id='77')]
                self.detail(**changes)
                with self.assertRaises(apify.PartialCollection): self.collect()
                self.assertEqual('incomplete', self.status('club')['last_status'])
                self.write.assert_not_called()

    def test_old_output_halts_before_extra_detail_spend(self):
        r = row(owner='partner', owner_id='77'); r['data']['taken_at_timestamp'] = 1000000000
        self.api.items.return_value = [r]
        with self.assertRaises(apify.CollectionHalted): self.collect()
        self.api.details.assert_not_called()
        self.assertEqual('incomplete', self.status('club')['last_status'])

    def test_aborted_feed_never_starts_details(self):
        self.api.items.return_value = [row(owner='partner', owner_id='77')]
        self.api.run.return_value['status'] = 'ABORTED'
        with self.assertRaises(apify.CollectionHalted): self.collect()
        self.api.details.assert_not_called()

    def test_low_time_does_not_defer_blocked_feed_or_hide_halt(self):
        for changes in ({'status': 'ABORTED'}, {'status': 'FAILED'},
                        {'options': {'maxTotalChargeUsd': .002}}):
            with self.subTest(changes=changes):
                self.api.items.return_value = [row(owner='partner', owner_id='77')]
                self.api.run.return_value = run(**changes)
                with patch.object(apify.time, 'monotonic', side_effect=[0, 280]):
                    with self.assertRaises(apify.PartialCollection) as raised:
                        self.collect()
                self.assertNotIsInstance(raised.exception, apify.CollectionDeferred)
                if changes.get('status') == 'ABORTED':
                    self.assertIsInstance(raised.exception, apify.CollectionHalted)
                self.assertTrue(json.loads(self.path.read_text())['consumed'])
                self.assertEqual('incomplete', self.status('club')['last_status'])
        self.api.details.assert_not_called()

    def test_low_time_without_required_details_still_finishes(self):
        with patch.object(apify.time, 'monotonic', side_effect=[0, 280]):
            self.collect()
        self.assertTrue(json.loads(self.path.read_text())['consumed'])
        self.assertEqual('ok', self.status('club')['last_status'])
        self.api.details.assert_not_called()

    def test_restricted_charge_halts_later_spending(self):
        self.api.run.return_value['chargedEventCounts']['restricted_post_scraped'] = 1
        with self.assertRaises(apify.CollectionHalted): self.collect()
        self.assertEqual('incomplete', self.status('club')['last_status'])

    def test_budget_cap_and_missing_pricing_do_not_advance(self):
        for changes in ({'options': {'maxTotalChargeUsd': .002}}, {'pricingInfo': {}}):
            with self.subTest(changes=changes):
                self.api.run.return_value = run(**changes)
                with self.assertRaises(apify.PartialCollection): self.collect()
                self.assertEqual('incomplete', self.status('club')['last_status'])

    def test_failed_detail_run_retains_only_affected_profile(self):
        self.api.items.return_value = [row(owner='partner', owner_id='77')]
        self.detail()
        self.api.details.return_value[0]['status'] = 'FAILED'
        with self.assertRaises(apify.PartialCollection): self.collect()
        self.assertEqual('incomplete', self.status('club')['last_status'])
        self.assertEqual('ok', self.status('quiet')['last_status'])
        self.assertIsNone(json.loads(self.path.read_text())['halt_reason'])

    def test_small_detail_run_uses_only_individual_post_headroom(self):
        self.api.items.return_value = [row(owner='partner', owner_id='77')]
        self.detail()
        detail_run = self.api.details.return_value[0]
        detail_run['options']['maxTotalChargeUsd'] = .004
        detail_run['chargedEventCounts'] = {'individual_post_scraped': 1, 'apify-actor-start': 1}
        self.collect()
        self.assertEqual('ok', self.status('club')['last_status'])
        self.write.assert_called_once()

    def test_missing_feed_options_uses_reserved_feed_ceiling(self):
        self.api.run.return_value = run(options={}, chargedEventCounts={
            'post_scraped': 14, 'apify-actor-start': 1})
        with self.assertRaisesRegex(apify.PartialCollection, 'charge ceiling'):
            apify.collect(self.api, ACCOUNTS, STATE, NOW, limit=100, max_charge=.02, timeout=300, archive=apify.ArchiveIndex())
        self.assertEqual('incomplete', self.status('club')['last_status'])

    def test_missing_coauthors_cannot_establish_unrelated_repost(self):
        self.api.items.return_value = [row(owner='partner', owner_id='77')]
        for value in ('missing', None, {}):
            with self.subTest(value=value):
                self.detail(coauthor_producers=value)
                if value == 'missing':
                    del self.api.details.return_value[1][0]['data']['coauthor_producers']
                with self.assertRaises(apify.PartialCollection):
                    self.collect()
                self.assertEqual('incomplete', self.status('club')['last_status'])
                self.assertEqual('ok', self.status('quiet')['last_status'])

    def test_malformed_detail_rows_do_not_strand_paid_batch(self):
        self.api.items.return_value = [row(owner='partner', owner_id='77')]
        self.detail()
        self.api.details.return_value[1][:] = [None, [], {'data': {'code': []}}]
        with self.assertRaises(apify.PartialCollection):
            self.collect()
        self.assertTrue(json.loads(self.path.read_text())['consumed'])
        self.assertEqual('incomplete', self.status('club')['last_status'])
        self.assertEqual('ok', self.status('quiet')['last_status'])

    def test_mirror_failure_keeps_paid_run_unconsumed_and_no_checkpoint_write(self):
        self.mirror.side_effect = RuntimeError('database unavailable')
        with self.assertRaisesRegex(RuntimeError, 'database unavailable'): self.collect()
        self.assertFalse(json.loads(self.path.read_text())['consumed'])
        self.upsert.assert_not_called()
        self.write.assert_not_called()


class HpixInputTests(unittest.TestCase):
    def test_new_run_uses_safe_flags_precise_filter_and_pinned_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            api = apify.ApifyClient('test', Path(tmp) / 'run.json')
            api.request = Mock(return_value={'data': run(startedAt=NOW.isoformat())})
            api.run({'username': ['club'], 'resultsLimit': 100,
                     'onlyPostsNewerThan': '2026-09-19T18:30:00Z'}, max_charge=1, timeout=60)
            call = api.request.call_args
            self.assertEqual(f'acts/{apify.HPIX_ACTOR_ID}/runs', call.args[1])
            payload = call.kwargs['json']
            self.assertEqual('2026-09-19', payload['fromDate'])
            self.assertIn('shouldSkip', payload['custom_functions'])
            self.assertIn('shouldContinue: () => true', payload['custom_functions'])
            self.assertNotIn('item.kind', payload['custom_functions'])
            self.assertTrue(payload['scrape_reels'])
            for flag in ('scrape_profile_data', 'scrape_detailed_data', 'scrape_restricted_posts'):
                self.assertFalse(payload[flag])
            self.assertEqual('1.2.17', call.kwargs['params']['build'])
            self.assertEqual(.8, call.kwargs['params']['maxTotalChargeUsd'])

    def test_log_cap_overrides_finish_even_with_filtered_dataset(self):
        text = 'INFO  Crawler: [club] Scraped 100/100 posts\nINFO  Crawler: [club] Finished scraping posts'
        self.assertEqual(set(), completed_profiles(text))

    def test_saved_official_run_resumes_without_new_hpix_purchase(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'run.json'
            path.write_text(json.dumps({'id': 'old-official', 'usernames': ['club'],
                                        'actor_id': apify.ACTOR_ID, 'consumed': False}))
            api = apify.ApifyClient('test', path)
            api.request = Mock(return_value={'data': run(actId=apify.ACTOR_ID)})
            api.run({'username': ['club'], 'resultsLimit': 100,
                     'onlyPostsNewerThan': '2026-09-19T18:30:00Z'}, max_charge=1, timeout=60)
            api.request.assert_called_once_with('GET', 'actor-runs/old-official')

    def test_detail_replay_uses_original_codes_and_does_not_buy_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            api = apify.ApifyClient('test', Path(tmp) / 'run.json')
            started = run(id='detail', startedAt=NOW.isoformat())
            with patch.object(apify.ApifyClient, 'request', side_effect=[
                    {'data': started}, {'data': started}]) as request, \
                 patch.object(apify.ApifyClient, 'items', return_value=[]):
                api.details(['A', 'B'], max_charge=.2, timeout=60)
                api.details(['B'], max_charge=.2, timeout=60)
            self.assertEqual(['POST', 'GET'], [call.args[0] for call in request.call_args_list])
            payload = request.call_args_list[0].kwargs['json']
            self.assertFalse(payload['scrape_detailed_data'])
            self.assertFalse(payload['scrape_restricted_posts'])
            self.assertEqual(2, len(payload['posts']))

    def test_ambiguous_detail_start_is_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            api = apify.ApifyClient('test', Path(tmp) / 'run.json')
            with patch.object(apify.ApifyClient, 'request', side_effect=TimeoutError('unknown')) as request:
                with self.assertRaises(TimeoutError): api.details(['A'], max_charge=.2, timeout=60)
                with self.assertRaisesRegex(RuntimeError, 'outcome unknown'):
                    api.details(['A'], max_charge=.2, timeout=60)
                request.assert_called_once()

    def test_failed_detail_replays_within_batch_but_fresh_cycle_can_retry(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(apify, 'RUNS_DIR', Path(tmp)), \
             patch.object(apify, 'POST_BACKFILL_SINCE', ''):
            first = apify.plan_jobs(ACCOUNTS, STATE, NOW, limit=100, max_charge=1)[0]
            second = apify.plan_jobs(ACCOUNTS, STATE, NOW, limit=100, max_charge=1)[0]
            api = apify.ApifyClient('test', Path(first['file']))
            retry_api = apify.ApifyClient('test', Path(second['file']))
            failed = run(id='failed-detail', status='FAILED', startedAt=NOW.isoformat())
            success = run(id='new-detail', startedAt=NOW.isoformat())
            with patch.object(apify.ApifyClient, 'request', side_effect=[
                    {'data': failed}, {'data': failed}, {'data': success}]) as request, \
                 patch.object(apify.ApifyClient, 'items', return_value=[]):
                api.details(['A'], max_charge=.2, timeout=60)
                replay, _ = api.details(['A'], max_charge=.2, timeout=60)
                retry, _ = retry_api.details(['A'], max_charge=.2, timeout=60)
            self.assertEqual(['POST', 'GET', 'POST'], [c.args[0] for c in request.call_args_list])
            self.assertEqual('failed-detail', replay['id'])
            self.assertEqual('new-detail', retry['id'])


class HpixPlanRecoveryTests(unittest.TestCase):
    def test_deferred_batch_stops_before_later_paid_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = [{'mode': 'discovery', 'handles': [h], 'cutoff': '2026-09-19T00:00:00Z',
                     'file': str(root / (h + '.json')), 'limit': 100, 'max_charge': .5,
                     'done': False} for h in ACCOUNTS]
            plan = {'jobs': jobs, 'complete': False}
            with patch.object(apify, 'PLAN_FILE', root / 'plan.json'), \
                 patch.object(apify, 'collect', side_effect=apify.CollectionDeferred('details pending')) as collect:
                with self.assertRaises(apify.CollectionDeferred):
                    apify.execute_plan('test', ACCOUNTS, STATE, NOW, plan, 300, archive=apify.ArchiveIndex())
            collect.assert_called_once()
            self.assertEqual(plan, apify.read_json(root / 'plan.json'))
            self.assertTrue(all(not job['done'] for job in jobs))

    def test_halt_preserves_consumed_batch_and_resume_does_not_buy_it_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = [{'mode': 'discovery', 'handles': [h], 'cutoff': '2026-09-19T00:00:00Z',
                     'file': str(root / (h + '.json')), 'limit': 100, 'max_charge': .5,
                     'done': False} for h in ACCOUNTS]
            plan = {'jobs': jobs, 'complete': False}
            def collect(api, accounts, *args, **kwargs):
                first = 'club' in accounts
                apify.write_json(api.run_file, {'consumed': True,
                    'errors': ['aborted'] if first else [],
                    'halt_reason': 'aborted' if first else None})
                if first:
                    raise apify.CollectionHalted('aborted')
            with patch.object(apify, 'PLAN_FILE', root / 'plan.json'), \
                 patch.object(apify, 'collect', side_effect=collect) as mocked:
                with self.assertRaises(apify.CollectionHalted):
                    apify.execute_plan('test', ACCOUNTS, STATE, NOW, plan, 300, archive=apify.ArchiveIndex())
                self.assertTrue(jobs[0]['done'])
                self.assertFalse(jobs[1]['done'])
                self.assertEqual(1, mocked.call_count)
                plan.pop('halt_reason')
                with self.assertRaises(apify.PartialCollection):
                    apify.execute_plan('test', ACCOUNTS, STATE, NOW, plan, 300, archive=apify.ArchiveIndex())
                self.assertEqual(2, mocked.call_count)
                self.assertTrue(plan['complete'])


class HpixBudgetPlanningTests(unittest.TestCase):
    def test_remainder_batches_have_a_usable_floor_without_overspend(self):
        jobs = [{'handles': list(range(size))} for size in [1, 4, 20, 22] + [25] * 24]
        apify._allocate(jobs, 1000)
        self.assertGreaterEqual(min(job['max_charge'] for job in jobs), .25)
        self.assertEqual(1000, sum(round(job['max_charge'] * 100) for job in jobs))

    def test_underfunded_plan_fails_before_assigning_tiny_caps(self):
        jobs = [{'handles': ['a']}, {'handles': ['b']}]
        with self.assertRaisesRegex(ValueError, 'budget'):
            apify._allocate(jobs, 49)
        self.assertTrue(all('max_charge' not in job for job in jobs))
        apify._allocate(jobs, 50)
        self.assertEqual([.25, .25], [job['max_charge'] for job in jobs])

    def test_stalest_cutoffs_go_first_including_within_an_hour(self):
        cutoffs = {'fresh': datetime(2026, 9, 20, tzinfo=timezone.utc),
                   'a_newer': datetime(2026, 9, 1, 0, 50, tzinfo=timezone.utc),
                   'z_oldest': datetime(2026, 9, 1, 0, 5, tzinfo=timezone.utc)}
        with patch.object(apify, 'BATCH_SIZE', 1):
            jobs = apify._group_jobs(cutoffs)
        self.assertEqual(['z_oldest', 'a_newer', 'fresh'], [job['handles'][0] for job in jobs])

    def test_aligned_roster_needs_seven_feed_starts(self):
        jobs = apify._group_jobs(dict.fromkeys([f'club{i}' for i in range(647)], NOW))
        self.assertEqual(7, len(jobs))
        self.assertEqual(647, sum(len(job['handles']) for job in jobs))
        self.assertLessEqual(max(len(job['handles']) for job in jobs), 100)

    def test_feed_retains_profile_failure_headroom(self):
        capped = run(options={'maxTotalChargeUsd': .016}, chargedEventCounts={
            'post_scraped': 14, 'apify-actor-start': 1})
        self.assertIn('charge ceiling', apify.charge_limit_reason(capped, .016, 14))

    def test_lagging_detail_counters_use_individual_price(self):
        capped = run(options={'maxTotalChargeUsd': .004}, chargedEventCounts={'apify-actor-start': 1})
        self.assertIn('charge ceiling', apify.charge_limit_reason(capped, .004, 2, details=True))

    def test_case_variants_cannot_hide_profile_failure_or_cap(self):
        finish = 'INFO  Crawler: [Club] Finished scraping posts'
        for reason in ('Failed to scrape profile club. The account may be private or restricted',
                       'INFO  Crawler: [CLUB] Scraped 100/100 posts'):
            with self.subTest(reason=reason):
                self.assertEqual(set(), completed_profiles(finish + '\n' + reason))
