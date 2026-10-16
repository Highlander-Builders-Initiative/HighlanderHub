"""Corrected reposts must keep their current source through publication replay."""
import copy
import itertools
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
from reconcile_events import Reviews, plan, prefer_repost_source
from test_sep25_duplicates import rows


def announcements():
    old, new = rows('ig_swe.ucr_p3992713400886284255-20260929T0000Z',
                    'ig_swe.ucr_p3992822134405002764-20260929T0000Z')
    old['image_url'] = 'https://example.org/original.jpg'
    new['image_url'] = 'https://example.org/corrected.jpg'
    return old, new


class RepostSourceTests(unittest.TestCase):
    def test_corrected_post_wins_in_every_order_and_replay(self):
        old, new = announcements()
        self.assertGreater(len(old['description']), len(new['description']))
        for ordered in itertools.permutations([old, new]):
            updates, removed, replacements = plan(list(ordered))
            self.assertEqual({old['id']: new['id']}, replacements)
            self.assertEqual({old['id']}, removed)
            survivor = updates[0] if updates else new
            for key in ('source_url', 'description', 'image_url', 'location'):
                self.assertEqual(new[key], survivor[key])
            self.assertEqual(replacements, plan([old, survivor])[2])
            self.assertEqual(([], set(), {}), plan([survivor]))

    def test_source_repair_preserves_identity_and_is_idempotent(self):
        old, new = announcements()
        fixed = prefer_repost_source(old, [old, new])
        self.assertEqual(old['id'], fixed['id'])
        self.assertEqual(new['source_url'], fixed['source_url'])
        self.assertEqual(new['description'], fixed['description'])
        self.assertEqual(new['image_url'], fixed['image_url'])
        self.assertEqual(new['location'], fixed['location'])
        self.assertEqual(fixed, prefer_repost_source(fixed, [old, new]))
        # Freshness belongs to the linked post, not the retained event ID.
        self.assertEqual(fixed, prefer_repost_source(fixed, [old]))

    def test_newer_incomplete_or_conflicting_posts_do_not_replace_source(self):
        old, new = announcements()
        old['location'] = new['location']
        for changes in ({'location': 'TBA'}, {'location': 'HUB 302'}, {'ends_at': None},
                        {'image_url': None}, {'description': ''}, {'host_handle': 'other'},
                        {'starts_at': '2026-09-30T00:00:00Z'}, {'all_day': True},
                        {'source_url': 'https://example.org/new'}, {'source': 'manual'}):
            with self.subTest(changes=changes):
                self.assertEqual(old, prefer_repost_source(old, [new | changes]))
        for field in ('has_free_food', 'rsvp_required', 'rsvp_url'):
            detailed = old | {field: 'https://example.org/rsvp' if field == 'rsvp_url' else True}
            self.assertEqual(detailed, prefer_repost_source(detailed, [new]))

    def test_standalone_announcement_does_not_take_a_newer_schedule_caption(self):
        old, new = announcements()
        old['id'] = old['id'].split('-')[0]
        self.assertEqual(old, prefer_repost_source(old, [new]))

    def test_conflicting_corrections_leave_the_original_for_review(self):
        old, new = announcements()
        conflicting = new | dict(id='ig_swe.ucr_p3993556542925612148-20260929T0000Z',
                                 source_url='https://www.instagram.com/p/Ddr9oRbhKR0/',
                                 location='HUB 302')
        self.assertEqual(old, prefer_repost_source(old, [new, conflicting]))

    def test_admin_choices_locks_and_distinct_decisions_protect_the_source(self):
        old, new = announcements()
        locked = old | {'is_locked': True}
        self.assertEqual(locked, prefer_repost_source(locked, [new]))
        for reviews in (Reviews({new['id']: old['id']}),
                        Reviews(distinct=frozenset({frozenset({old['id'], new['id']})}))):
            self.assertEqual(old, prefer_repost_source(old, [new], reviews=reviews))
        self.assertEqual({new['id']: old['id']},
                         plan([old, new], reviews=Reviews({new['id']: old['id']}))[2])
        self.assertEqual({new['id']: old['id']}, plan([locked, new])[2])
        self.assertEqual(([], {new['id']}, {}), plan([new], [old]))

    def test_publication_keeps_correction_when_newer_repeat_is_withheld(self):
        old, new = announcements()
        payload = {'status': 'complete', 'result': {}}
        keys = ['instagram:post:3992713400886284255', 'instagram:post:3992822134405002764']
        updates = [{'source_key': key, 'assessment': payload, 'rows': [row]}
                   for key, row in zip(keys, [old, new])]
        registry = {key: {'assessment': payload, 'event_ids': [old['id']],
                          'known_event_ids': [old['id'], new['id']]} for key in keys}
        before = copy.deepcopy(updates)
        fixed = prefer_repost_source(old, [new])
        result = publication._withhold_reconciled(copy.deepcopy(updates), registry, {old['id']: fixed})
        self.assertEqual(1, len(result))
        published = result[0]['rows'][0]
        self.assertEqual(old['id'], published['id'])
        for key in ('source_url', 'description', 'image_url', 'location'):
            self.assertEqual(new[key], published[key])
        self.assertEqual(result, publication._withhold_reconciled(
            copy.deepcopy(updates), registry, {old['id']: published}))
        protected = publication._withhold_reconciled(
            copy.deepcopy(updates), registry, {old['id']: old},
            reviews=Reviews({new['id']: old['id']}))
        self.assertEqual(old['source_url'], protected[0]['rows'][0]['source_url'])
        self.assertEqual(before, updates)

    def test_unmerged_past_sessions_get_source_correction_during_publication(self):
        # Schedule posts can still publish their past sessions while other
        # sessions are upcoming. Reconciliation deliberately skips past events.
        old, new = announcements()
        updates = [{'source_key': f'instagram:post:{i}', 'assessment': {}, 'rows': [row]}
                   for i, row in enumerate([old, new])]
        result = publication._withhold_reconciled(updates, {}, {})
        self.assertEqual([old['id'], new['id']], [u['rows'][0]['id'] for u in result])
        self.assertTrue(all(u['rows'][0]['source_url'] == new['source_url'] for u in result))

    def test_publication_loads_admin_decisions_before_correcting_unmerged_posts(self):
        with patch.object(publication, 'load_registry', return_value={}), \
             patch.object(publication, '_canonical_listings', return_value={}), \
             patch.object(publication, 'post_updates', return_value=[]) as updates, \
             patch.object(publication, 'publish', return_value={}), \
             patch('reconcile_events.load_reviews', return_value=(Reviews(), [])) as load:
            publication.publish_posts([({}, {}), ({}, {})], '2026-09-26T17:00:00Z', meta={}, notify=False)
        load.assert_called_once_with()
        self.assertEqual(Reviews(), updates.call_args.kwargs['reviews'])


class WithdrawnSourceTests(unittest.TestCase):
    """The older post's listing outlives that post on its repeat's support."""

    OLD, NEW = 'instagram:post:3992713400886284255', 'instagram:post:3992822134405002764'
    PAYLOAD = {'status': 'complete', 'result': {}}

    def merged(self):
        old, new = announcements()
        # A newer repeat without a flyer does not replace the original.
        new['image_url'] = None
        updates, removed, replacements = plan([old, new])
        self.assertEqual({new['id']: old['id']}, replacements)
        listing = updates[0] if updates else old
        # remap_assessed_event_sources moved the repeat's support onto the listing.
        registry = {self.OLD: {'assessment': self.PAYLOAD, 'event_ids': [old['id']],
                               'known_event_ids': [old['id']]},
                    self.NEW: {'assessment': self.PAYLOAD, 'event_ids': [old['id']],
                               'known_event_ids': [new['id'], old['id']]}}
        return old, new, listing, registry

    def withdraw(self, registry):
        import post_recheck
        update = post_recheck.withdrawal(self.OLD, registry[self.OLD],
                                         datetime(2026, 9, 27, tzinfo=timezone.utc))
        # reconcile_source_assessments: no rows, so the post supports nothing.
        registry[self.OLD] = {'assessment': update['assessment'], 'event_ids': [],
                              'known_event_ids': update['known_event_ids']}

    def republish(self, new, registry, canonical, **kwargs):
        # post_updates skips the withdrawn post; only the repeat is processed.
        update = {'source_key': self.NEW, 'origin': 'instagram', 'assessment': self.PAYLOAD,
                  'rows': [copy.deepcopy(new)], 'known_event_ids': []}
        return publication._withhold_reconciled([update], registry, canonical, **kwargs)

    def test_listing_links_to_the_surviving_post_after_withdrawal(self):
        old, new, listing, registry = self.merged()
        self.withdraw(registry)
        stats = {}
        result = self.republish(new, registry, {old['id']: listing}, stats=stats)
        self.assertEqual([self.NEW], [update['source_key'] for update in result])
        [published] = result[0]['rows']
        self.assertEqual(old['id'], published['id'])
        for key in ('source_url', 'description', 'image_url'):
            self.assertEqual(new[key], published[key], key)
        self.assertIsNone(published['image_url'])
        for key in ('title', 'starts_at', 'ends_at', 'location'):
            self.assertEqual(listing[key], published[key], key)
        self.assertNotIn('hosts', published)
        self.assertEqual(1, stats['withdrawn_sources_replaced'])
        # The next run republishes the same row, and nothing is left to merge.
        self.assertEqual(result, self.republish(new, registry, {old['id']: published}))
        self.assertEqual(([], set(), {}), plan([published]))

    def test_listing_is_left_alone_while_its_post_is_up(self):
        old, new, listing, registry = self.merged()
        self.assertEqual([], self.republish(new, registry, {old['id']: listing}))

    def test_locked_listing_and_distinct_decision_keep_the_listing(self):
        old, new, listing, registry = self.merged()
        self.withdraw(registry)
        locked = listing | {'is_locked': True}
        self.assertEqual([], self.republish(new, registry, {old['id']: locked}))
        distinct = Reviews(distinct=frozenset({frozenset({old['id'], new['id']})}))
        self.assertEqual([], self.republish(new, registry, {old['id']: listing}, reviews=distinct))

    def test_admin_merge_keeps_the_listing_id_and_takes_the_surviving_source(self):
        old, new, listing, registry = self.merged()
        self.withdraw(registry)
        result = self.republish(new, registry, {old['id']: listing},
                                reviews=Reviews({new['id']: old['id']}))
        [published] = result[0]['rows']
        self.assertEqual(old['id'], published['id'])
        self.assertEqual(new['source_url'], published['source_url'])


if __name__ == '__main__':
    unittest.main()
