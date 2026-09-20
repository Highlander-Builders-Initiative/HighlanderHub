import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluate_apify_monitor import evaluate, hpix_item

BASE = {'inputUrl': 'https://www.instagram.com/club', 'id': '123',
        'shortCode': 'abc', 'timestamp': '2026-09-02T00:00:00Z', 'type': 'Image',
        'caption': 'Event', 'ownerUsername': 'club', 'ownerId': '42',
        'displayUrl': 'https://example.com/image.jpg'}
POST = {'recordType': 'post', 'username': 'club', 'postId': '123',
        'shortcode': 'abc', 'publishedAt': '2026-09-02T00:00:00Z', 'postType': 'image',
        'caption': 'Event', 'owner': {'id': '42', 'username': 'club'},
        'displayUrl': 'https://example.com/image.jpg', 'children': [], 'coauthors': []}


class MonitorEvaluationTests(unittest.TestCase):
    def evaluate(self, rows, log='', reference=None, seen=()):
        return evaluate(reference or [BASE], rows, log, ['club'], '2026-09-01T00:00:00Z', seen)

    def test_reachable_preview_does_not_prove_complete_coverage(self):
        result = self.evaluate([POST], 'INFO club: profile=false, posts=1, source=web-profile-api.')
        self.assertEqual(1, result['reference_recall']['rate'])
        self.assertFalse(result['pagination_to_cutoff_verified'])
        self.assertFalse(result['production_approved'])
        self.assertIsNone(result['fidelity']['carousel']['rate'])

    def test_unavailable_and_silence_are_not_successful_quiet_checks(self):
        for log in ('WARN club: profile unavailable; no rows charged.', ''):
            result = self.evaluate([], log)
            self.assertEqual(0, result['preview_success']['rate'])
            self.assertEqual(['abc'], result['profiles'][0]['missing_shortcodes'])
            self.assertFalse(result['profiles'][0]['false_quiet'])

    def test_false_quiet_requires_positive_reference_and_zero_result_claim(self):
        result = self.evaluate([], 'INFO club: profile=false, posts=0, source=web-profile-api.')
        self.assertEqual(1, result['false_quiet']['rate'])

    def test_intentionally_suppressed_seen_posts_are_not_missing(self):
        result = self.evaluate([], 'INFO club: profile=false, posts=0, source=web-profile-api.', seen=['abc'])
        self.assertEqual(0, result['reference_recall']['denominator'])
        self.assertFalse(result['profiles'][0]['false_quiet'])
        result = self.evaluate([POST], seen=['abc'])
        self.assertEqual(1, result['seen_shortcode_exports'])

    def test_missing_details_are_not_silently_defaulted(self):
        post = dict(POST)
        del post['coauthors']
        result = self.evaluate([post])
        self.assertEqual(0, result['contract_valid_rows']['rate'])
        self.assertEqual('missing coauthors', result['contract_failures'][0]['reason'])

    def test_reordered_carousel_and_missing_coauthors_fail_fidelity(self):
        base = {**BASE, 'type': 'Sidecar', 'coauthorProducers': [{'id': '7', 'username': 'partner'}],
                'childPosts': [{**BASE, 'id': '1'}, {**BASE, 'id': '2'}]}
        post = copy.deepcopy(POST)
        post.update(postType='carousel', children=[{**POST, 'postId': '2'}, {**POST, 'postId': '1'}])
        result = self.evaluate([post], reference=[base])
        self.assertEqual(0, result['fidelity']['carousel']['rate'])
        self.assertEqual(0, result['fidelity']['coauthors']['rate'])

    def test_duplicate_exports_do_not_inflate_recall(self):
        result = self.evaluate([POST, POST])
        self.assertEqual(1, result['reference_recall']['numerator'])
        self.assertEqual(1, result['duplicate_exports_within_run'])

    def test_matching_shortcode_does_not_hide_wrong_owner_id(self):
        post = {**POST, 'owner': {'id': '99', 'username': 'club'}}
        result = self.evaluate([post])
        self.assertEqual(0, result['fidelity']['owner']['rate'])


def hpix_node(**overrides):
    node = {'__typename': 'GraphImage', 'id': '123', 'shortcode': 'abc',
            'taken_at_timestamp': 1788307200, 'owner': {'id': '42', 'username': 'club'},
            'coauthor_producers': [], 'is_video': False,
            'edge_media_to_caption': {'edges': [{'node': {'text': 'Event'}}]},
            'display_resources': [{'src': 'https://example.com/a.jpg', 'config_width': 640,
                                   'config_height': 640}]}
    node.update(overrides)
    return {'kind': 'post', 'input': 'club', 'data': node}


ARCHIVE = {'handle': 'club', 'media_id': '123', 'owner_username': 'club', 'owner_userid': '42',
           'shortcode': 'abc', 'posted_at': '2026-09-02T00:00:00+00:00', 'typename': 'GraphImage',
           'caption': 'Event', 'has_video': False,
           'media': [{'index': 0, 'is_video': False, 'image_url': 'https://example.com/a.jpg',
                      'media_key': 'a'}]}
SCAN = ('INFO  Crawler: [club] Scraped 1/30 posts\n'
        'INFO  Crawler: [club] Stopping at post OLD (taken at 2026-08-30T00:00:00.000Z)\n'
        'INFO  Crawler: [club] Finished scraping posts\n')


class HpixEvaluationTests(unittest.TestCase):
    def evaluate(self, rows, log=SCAN, reference=None, seen=()):
        return evaluate(reference or [ARCHIVE], rows, log, ['club'], '2026-09-01T00:00:00Z', seen,
                        candidate_format='hpix', reference_format='archive')

    def test_profile_feed_node_matches_the_production_archive(self):
        result = self.evaluate([hpix_node()])
        self.assertEqual(1, result['reference_recall']['rate'])
        self.assertEqual(1, result['contract_valid_rows']['rate'])
        self.assertTrue(result['pagination_to_cutoff_verified'])
        self.assertFalse(result['production_approved'])
        for field in ('id', 'owner', 'type', 'timestamp', 'caption'):
            self.assertEqual(1, result['fidelity'][field]['rate'], field)

    def test_null_profile_row_outranks_a_finish_line(self):
        rows = [hpix_node(), {'kind': 'profile', 'input': 'club', 'data': None}]
        result = self.evaluate(rows)
        self.assertEqual(['club'], result['retrieval_failures'])
        self.assertEqual(0, result['scan_completed']['rate'])
        self.assertEqual(0, result['preview_success']['rate'])
        self.assertFalse(result['pagination_to_cutoff_verified'])
        self.assertFalse(result['profiles'][0]['false_quiet'])

    def test_finishing_above_the_cutoff_is_not_a_scan_to_the_cutoff(self):
        log = ('INFO  Crawler: [club] Scraped 1/30 posts\n'
               'INFO  Crawler: [club] Stopping at post NEW (taken at 2026-09-03T00:00:00.000Z)\n'
               'INFO  Crawler: [club] Finished scraping posts\n')
        result = self.evaluate([hpix_node()], log=log)
        self.assertEqual(0, result['scan_completed']['rate'])
        self.assertFalse(result['pagination_to_cutoff_verified'])

    def test_silence_about_a_profile_is_not_a_quiet_check(self):
        result = self.evaluate([], log='')
        self.assertEqual(0, result['preview_success']['rate'])
        self.assertEqual(['abc'], result['profiles'][0]['missing_shortcodes'])
        self.assertFalse(result['profiles'][0]['false_quiet'])

    def test_explicit_zero_for_a_profile_with_reference_posts_is_false_quiet(self):
        log = ('INFO  Crawler: [club] Scraped 0/30 posts\n'
               'INFO  Crawler: [club] Finished scraping posts\n')
        result = self.evaluate([], log=log)
        self.assertEqual(1, result['false_quiet']['rate'])

    def test_missing_graphql_fields_are_not_silently_defaulted(self):
        for field in ('coauthor_producers', 'edge_media_to_caption', 'owner', 'display_resources'):
            node = hpix_node()
            del node['data'][field]
            result = self.evaluate([node])
            self.assertEqual(0, result['contract_valid_rows']['rate'], field)
            self.assertEqual(f'missing {field}', result['contract_failures'][0]['reason'])

    def test_carousel_children_must_keep_their_order(self):
        def child(name):
            return {'is_video': False,
                    'display_resources': [{'src': f'https://example.com/{name}.jpg',
                                           'config_width': 640, 'config_height': 640}]}
        reference = copy.deepcopy(ARCHIVE)
        reference['typename'] = 'GraphSidecar'
        reference['media'] = [{'index': 0, 'is_video': False, 'media_key': 'a',
                               'image_url': 'https://example.com/a.jpg'},
                              {'index': 1, 'is_video': False, 'media_key': 'b',
                               'image_url': 'https://example.com/b.jpg'}]
        node = hpix_node(__typename='GraphSidecar', edge_sidecar_to_children={
            'edges': [{'node': child('b')}, {'node': child('a')}]})
        result = self.evaluate([node], reference=[reference])
        self.assertEqual(0, result['fidelity']['carousel']['rate'])

    def test_a_feed_post_owned_by_a_stranger_is_not_attributed_to_the_club(self):
        node = hpix_node(owner={'id': '99', 'username': 'someoneelse'})
        result = self.evaluate([node])
        self.assertEqual(0, result['contract_valid_rows']['rate'])
        self.assertIn('owner/accepted coauthor', result['contract_failures'][0]['reason'])

    def test_a_verified_coauthor_restores_club_attribution(self):
        node = hpix_node(owner={'id': '99', 'username': 'someoneelse'},
                         coauthor_producers=[{'id': '42', 'username': 'club'}])
        self.assertEqual('club', hpix_item(node)['coauthor_producers'][0]['username'])
        result = self.evaluate([node])
        self.assertEqual(1, result['contract_valid_rows']['rate'])
        self.assertEqual(1, result['reference_recall']['rate'])


if __name__ == '__main__':
    unittest.main()
