"""A club's flyer announcement stays the listing; later reels only add details.

Clubs post one announcement with a flyer, then reels as the event nears. A
reel is read from its caption and one video frame, so it must not take the
listing over, but the time it adds or corrects belongs on the listing.
"""
import copy
import itertools
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
from reconcile_events import (_SHORTCODE_ALPHABET, _announces_change, merge_duplicates, plan,
                              prefer_repost_source, retimed_candidates, review_candidates, same_event)

NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)
SIX_PM, SEVEN_PM = '2026-12-05T02:00:00+00:00', '2026-12-05T03:00:00+00:00'  # Dec 4, Pacific
DEC_4, DEC_5, DEC_11 = ('2026-12-04T08:00:00+00:00', '2026-12-05T08:00:00+00:00',
                        '2026-12-11T08:00:00+00:00')


def _permalink(media: int) -> str:
    code = ''
    while media:
        media, digit = divmod(media, 64)
        code = _SHORTCODE_ALPHABET[digit] + code
    return f'https://www.instagram.com/p/{code}/'


def post(media: int, **extra) -> dict:
    return {
        'id': f'ig_club_p{media}', 'title': 'Diwali Night', 'description': 'Join us for Diwali Night!',
        'starts_at': SIX_PM, 'ends_at': None, 'all_day': False, 'location': 'HUB 302',
        'host': 'Club', 'host_handle': 'club', 'category': 'hangout', 'content_kind': 'student_event',
        'tags': [], 'source': 'instagram', 'source_url': _permalink(media),
        'image_url': f'https://example.org/{media}.jpg', 'image_is_video': None,
        'has_free_food': False, 'rsvp_required': False, 'rsvp_url': None,
        'scraped_at': '2026-11-20T00:00:00+00:00', **extra,
    }


def flyer(**extra) -> dict:
    return post(4000000000000000001, **extra)


def reel(**extra) -> dict:
    # A reel's caption is usually the longer one, which used to win the listing.
    return post(4000000000000000002, **{'image_is_video': True, 'description': (
        'Diwali Night is THIS week!! Come through for food, music and dancing with all of us. '
        'Bring your friends, wear your best fit and get ready for the best night of the quarter.'),
        **extra})


def survivor(rows: list[dict]) -> dict:
    """The one listing a group reconciles to, in every order and on replay."""
    expected = plan(copy.deepcopy(rows))
    updates, removed, _ = expected
    for ordered in itertools.permutations(rows):
        assert plan(copy.deepcopy(list(ordered))) == expected
    left = [row for row in rows if row['id'] not in removed]
    assert len(left) == 1, [row['id'] for row in left]
    kept = next((row for row in updates if row['id'] == left[0]['id']), left[0])
    assert plan([kept]) == ([], set(), {})
    return kept


class FollowUpReelTests(unittest.TestCase):
    def test_announcement_keeps_its_flyer_caption_and_link(self):
        old, new = flyer(), reel(ends_at='2026-12-05T05:00:00+00:00', rsvp_url='https://forms.example.com/diwali')
        kept = survivor([old, new])
        self.assertEqual(old['id'], kept['id'])
        for key in ('image_url', 'description', 'source_url', 'image_is_video'):
            self.assertEqual(old[key], kept[key], key)
        # What the announcement lacked still comes from the reel.
        self.assertEqual(new['ends_at'], kept['ends_at'])
        self.assertEqual(new['rsvp_url'], kept['rsvp_url'])

    def test_without_the_flag_the_longer_caption_still_wins(self):
        # The rule turns on what the image is, not on which post is newer.
        old, new = flyer(), reel(image_is_video=None)
        self.assertEqual(new['id'], survivor([old, new])['id'])

    def test_a_reel_is_not_a_corrected_repost(self):
        old, new = flyer(), reel()
        self.assertEqual(old, prefer_repost_source(old, [old, new]))
        still = reel(image_is_video=None)
        self.assertEqual(still['image_url'], prefer_repost_source(old, [old, still])['image_url'])

    def test_reel_gives_the_time_a_date_only_announcement_left_out(self):
        old = flyer(starts_at=DEC_4, ends_at=DEC_5, all_day=True, location='')
        new = reel(ends_at='2026-12-05T05:00:00+00:00')
        self.assertTrue(same_event(old, new))
        kept = survivor([old, new])
        self.assertEqual(old['id'], kept['id'])
        self.assertEqual(old['image_url'], kept['image_url'])
        self.assertEqual((SIX_PM, new['ends_at'], False), (kept['starts_at'], kept['ends_at'], kept['all_day']))
        self.assertEqual('HUB 302', kept['location'])

    def test_a_timed_still_post_becomes_the_listing_as_before(self):
        old = flyer(starts_at=DEC_4, ends_at=DEC_5, all_day=True, location='')
        new = reel(image_is_video=None)
        self.assertEqual(new['id'], survivor([old, new])['id'])

    def test_a_schedule_line_is_not_the_announcement(self):
        # The reel about this one event names it better than a schedule
        # post's line does; it only borrows the schedule's still image.
        line = flyer(id='ig_club_p4000000000000000001-20261205T0200Z')
        kept = survivor([line, reel()])
        self.assertEqual((reel()['id'], reel()['description'], line['image_url'], None),
                         (kept['id'], kept['description'], kept['image_url'], kept['image_is_video']))

    def test_reels_that_disagree_fill_no_time(self):
        old = flyer(starts_at=DEC_4, ends_at=DEC_5, all_day=True)
        late = post(4000000000000000003, image_is_video=True, starts_at=SEVEN_PM)
        merged = merge_duplicates(old, [old, reel(), late])
        self.assertEqual((DEC_4, DEC_5, True), (merged['starts_at'], merged['ends_at'], merged['all_day']))

    def test_reel_listing_takes_back_its_accounts_earliest_flyer(self):
        # A reel that became the listing before this rule gets its flyer back
        # when publication replays the merge.
        old, new = flyer(), reel()
        later = post(4000000000000000003, image_url='https://example.org/second.jpg')
        merged = merge_duplicates(new, [new, later, old])
        self.assertEqual((old['image_url'], None), (merged['image_url'], merged['image_is_video']))
        partner = flyer(id='ig_partner_p4000000000000000001', host_handle='partner')
        self.assertEqual(partner['image_url'], merge_duplicates(new, [new, partner])['image_url'])
        # Two partners' flyers name no single one.
        other = post(4000000000000000004, id='ig_other_p4000000000000000004', host_handle='other')
        self.assertEqual(new['image_url'], merge_duplicates(new, [new, partner, other])['image_url'])


class RescheduledTests(unittest.TestCase):
    CHANGE = 'TIME CHANGE: doors now open at 7 PM for Diwali Night. See you there!'

    def test_reel_announcing_a_new_time_updates_the_announcement(self):
        old = flyer(ends_at='2026-12-05T04:00:00+00:00')
        new = reel(starts_at=SEVEN_PM, description=self.CHANGE)
        self.assertTrue(same_event(old, new))
        kept = survivor([old, new])
        self.assertEqual((old['id'], old['image_url']), (kept['id'], kept['image_url']))
        # The replaced time's end does not survive the move.
        self.assertEqual((SEVEN_PM, None), (kept['starts_at'], kept['ends_at']))

    def test_still_post_announcing_a_new_time_becomes_the_listing(self):
        old = flyer()
        new = post(4000000000000000002, starts_at=SEVEN_PM, description=self.CHANGE)
        kept = survivor([old, new])
        self.assertEqual((new['id'], new['image_url'], SEVEN_PM),
                         (kept['id'], kept['image_url'], kept['starts_at']))

    def test_another_time_without_saying_so_is_only_asked_about(self):
        old, new = flyer(), reel(starts_at=SEVEN_PM)
        self.assertFalse(same_event(old, new))
        self.assertEqual(([], set(), {}), plan([old, new]))
        self.assertEqual([(old, new)], review_candidates([old, new], now=NOW))
        # Two still posts at different times may be two showings.
        still = reel(starts_at=SEVEN_PM, image_is_video=None)
        self.assertEqual([], review_candidates([old, still], now=NOW))

    def test_a_change_needs_the_same_event_and_account(self):
        old = flyer()
        for changes in ({'title': 'Holi Night'}, {'host_handle': 'other', 'id': 'ig_other_p4000000000000000002'},
                        {'title': 'Diwali Night Part 2'}):
            with self.subTest(changes=changes):
                new = reel(starts_at=SEVEN_PM, description=self.CHANGE, **changes)
                self.assertFalse(same_event(old, new))

    def test_an_older_post_never_reschedules_a_newer_one(self):
        old = flyer(description=self.CHANGE)
        self.assertFalse(same_event(old, reel(starts_at=SEVEN_PM)))

    def test_move_to_another_day_is_asked_about_never_merged(self):
        old = flyer()
        new = reel(starts_at='2026-12-12T02:00:00+00:00',
                   description='Diwali Night has been RESCHEDULED to Friday, December 11!')
        self.assertFalse(same_event(old, new))
        self.assertEqual(([], set(), {}), plan([old, new]))
        self.assertEqual([(old, new)], retimed_candidates([old, new], now=NOW))
        self.assertEqual([], review_candidates([old, new], now=NOW))

    def test_next_weeks_meeting_is_not_a_rescheduling(self):
        old = flyer()
        moved = dict(starts_at='2026-12-12T02:00:00+00:00')
        rescheduled = 'RESCHEDULED to Friday, December 11!'
        for label, new in (
                ('says nothing', reel(**moved)),
                ('generic title', reel(title='General Meeting', description=rescheduled, **moved)),
                ('another event', reel(title='Holi Night', description=rescheduled, **moved)),
                ('months away', reel(starts_at='2027-01-16T02:00:00+00:00', description=rescheduled))):
            with self.subTest(label):
                first = old | {'title': new['title']} if label == 'generic title' else old
                self.assertEqual([], retimed_candidates([first, new], now=NOW))

    def test_corrected_deadline_keeps_the_flyer_and_takes_the_reels_date(self):
        form = 'https://forms.example.com/apply'
        old = flyer(title='Board Application Deadline', content_kind='student_deadline',
                    starts_at=DEC_4, ends_at=DEC_5, all_day=True, rsvp_url=form)
        new = reel(title='Board Application Deadline', content_kind='student_deadline',
                   starts_at=DEC_11, ends_at='2026-12-12T08:00:00+00:00', all_day=True, rsvp_url=form)
        kept = survivor([old, new])
        self.assertEqual((old['id'], old['image_url'], DEC_11, new['ends_at']),
                         (kept['id'], kept['image_url'], kept['starts_at'], kept['ends_at']))

    def test_change_wording(self):
        for caption in ('TIME CHANGE: now at 7', 'We have rescheduled!', 'Re-scheduled for next week',
                        'Postponed until Friday', 'date change!!', 'Please note the updated time',
                        'NEW TIME: 7 PM', 'new date, same great food', 'Change of date for our gala',
                        'We moved it to Thursday', 'Pushed back an hour', 'moved to 7pm',
                        'Our event is moving to Dec 11', 'DATE CHANGED: officially on THURSDAY',
                        'WE WILL BE POSTPONING OUR CTF NIGHT TO FRIDAY, NOVEMBER 6'):
            self.assertTrue(_announces_change({'description': caption}), caption)
        for caption in ('Join us at 7 PM', 'New time slot added', 'new times available', 'We moved to HUB 302',
                        'A new date night idea', 'Save the date', 'time to change the world',
                        'Spider-Man: Brand New Day is swinging onto campus',
                        'New date added: Dec 11'):
            self.assertFalse(_announces_change({'description': caption}), caption)


class PublicationTests(unittest.TestCase):
    def rows(self, is_video: bool) -> list[dict]:
        text = 'Study Jam September 15, 2026 3 PM-5 PM'
        record = {'media_id': '700', 'handle': 'acm.ucr', 'owner_username': 'acm.ucr',
                  'permalink': 'https://www.instagram.com/p/CStudy/', 'posted_at': '2026-09-10T17:00:00+00:00',
                  'caption': 'Join ACM for a study jam',
                  'media': [{'index': 0, 'media_key': '700_0_n', 'is_video': is_video,
                             'image_url': 'https://cdn.example/700_0_n.jpg'}]}
        cached = {'status': 'ok', 'images': [{'media_key': '700_0_n', 'index': 0, 'ocr_text': text,
                                              'qr_urls': [], 'image_url': 'https://storage.example/700_0_n.jpg'}]}
        cited = [{'field': 'slide_1_ocr', 'quote': text}]
        payload = {'status': 'complete', 'source': publication.post_source(record, cached), 'result': {
            'kind': 'activity', 'date_role': 'occurrence', 'reason': 'Flyer announces a study jam.',
            'activity_evidence': cited, 'date_evidence': cited, 'use_source_occurrences': False,
            'schedule': None, 'occurrences': [{
                'title': 'Study Jam', 'starts_at': '2026-09-15T15:00:00-07:00',
                'ends_at': '2026-09-15T17:00:00-07:00', 'all_day': False, 'location': '',
                'activity_evidence': cited, 'date_evidence': cited}]}}
        return publication.post_rows(record, cached, payload, {}, '2026-09-11T12:00:00+00:00')[0]

    def test_a_video_slides_cover_is_marked_and_a_still_is_not(self):
        self.assertIs(True, self.rows(True)[0]['image_is_video'])
        self.assertIsNone(self.rows(False)[0]['image_is_video'])

    def test_replayed_merge_keeps_the_time_the_reel_gave(self):
        # The announcement's own post still says "date only" on every run.
        old = flyer(starts_at=DEC_4, ends_at=DEC_5, all_day=True)
        new = reel(ends_at='2026-12-05T05:00:00+00:00')
        listing = survivor([old, new])
        payload = {'status': 'complete', 'result': {}}
        keys = [f"instagram:post:{row['id'].rsplit('_p', 1)[1]}" for row in (old, new)]
        registry = {keys[0]: {'assessment': payload, 'event_ids': [old['id']], 'known_event_ids': [old['id']]},
                    keys[1]: {'assessment': payload, 'event_ids': [old['id']],
                              'known_event_ids': [new['id'], old['id']]}}
        updates = [{'source_key': key, 'assessment': payload, 'rows': [row]}
                   for key, row in zip(keys, (old, new))]
        result = publication._withhold_reconciled(copy.deepcopy(updates), registry, {old['id']: listing})
        self.assertEqual([[old['id']]], [[row['id'] for row in update['rows']] for update in result])
        published = result[0]['rows'][0]
        for key in ('starts_at', 'ends_at', 'all_day', 'image_url', 'description', 'source_url'):
            self.assertEqual(listing[key], published[key], key)


if __name__ == '__main__':
    unittest.main()
