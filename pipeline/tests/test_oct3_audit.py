"""Source-backed regressions from the October 3 pipeline audit."""
import copy
import io
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import content_assessment as semantic
import assessed_events as publication
import extract_posts as extraction
import reconcile_events as reconcile
from event_dates import evidence_dates
from classify import detect_free_food

CASES = json.loads((Path(__file__).parent / 'fixtures/oct3-sources.json').read_text())
REVIEWS = json.loads((Path(__file__).parent / 'fixtures/oct3-reviews.json').read_text())


class FoodEvidenceTests(unittest.TestCase):
    def test_admission_charge_applies_to_included_drinks_on_the_next_line(self):
        self.assertFalse(detect_free_food('Price will be $10 at the door which is subject to increase!\nDrinks are included and members get in free'))
        self.assertFalse(detect_free_food('Admission: $5\nPizza included'))
        self.assertTrue(detect_free_food('Bake sale $3\nPIZZA INCLUDED'))
        self.assertTrue(detect_free_food('Free admission\nPizza included'))
        self.assertTrue(detect_free_food('GBM tonight 7pm\nPizza included!\nRaffle tickets $1 each'))
        self.assertTrue(detect_free_food('First GBM 7pm\nDinner included\nMembership fee: $20 for the year'))
        self.assertFalse(detect_free_food('Banquet\nRegistration fee: $20\nDinner included'))

    def test_labeled_meal_offers_preserve_negation_and_price_checks(self):
        for food in ('Panera Breakfast', 'Boba Drinks', 'El Pollo Loco', 'Michis de la Baja',
                     'Panera Lunch', 'Drinks & Desserts', 'Brunch'):
            with self.subTest(food=food):
                self.assertTrue(detect_free_food('FREE: ' + food))
                self.assertFalse(detect_free_food('No free: ' + food))
        for text in ('FREE: Planners', 'FREE: Admission', 'Free: boba with a purchase', 'Free: brunch costs $5'):
            self.assertFalse(detect_free_food(text))


class DateEvidenceTests(unittest.TestCase):
    def test_application_cutoff_without_clock_is_a_date(self):
        case = CASES['asme']
        result = semantic.validate(semantic._attach_source_quotes(
            copy.deepcopy(case['result']), case['source']), case['source'])
        self.assertEqual('2026-10-09T00:00:00-07:00', result['occurrences'][0]['starts_at'])
        self.assertEqual('2026-10-10T00:00:00-07:00', result['occurrences'][0]['ends_at'])
        for text in ('Apps due 1/2 price', 'Room 10/9', 'Applications due 1/2 of a page',
                     'Applications due 1/2\nof a page', 'Use 1/2\nof milk at 3pm'):
            self.assertEqual(set(), evidence_dates(text), text)

    def test_interleaved_title_does_not_erase_weekday_date(self):
        source = CASES['rbrains']['source']
        self.assertTrue(semantic._day_supported(date(2026, 11, 17), source['texts']['slide_2_ocr'], source))
        self.assertEqual(set(), evidence_dates('Use 1/2 cup milk at 7pm'))

    def test_korean_month_and_day_preserve_year_grounding(self):
        case = CASES['hanwave']
        semantic.validate(semantic._attach_source_quotes(copy.deepcopy(case['result']), case['source']), case['source'])
        for text in ('2026년 10월 9일', '일시: 2026년 10월 9일(금)'):
            self.assertTrue(semantic._day_supported(date(2026, 10, 9), text, {}))
            self.assertFalse(semantic._day_supported(date(2027, 10, 9), text, {}))
        self.assertEqual(set(), evidence_dates('10월 99일'))
        self.assertFalse(semantic._day_supported(date(2026, 10, 8), '10월 9일', case['source']))


class LocationEvidenceTests(unittest.TestCase):
    def test_location_lookup_is_not_the_venue(self):
        case = CASES['location_pointer']
        with self.assertRaisesRegex(ValueError, 'where to find the venue'):
            semantic.validate(semantic._attach_source_quotes(copy.deepcopy(case['result']), case['source']), case['source'])
        for name, text in (('Canvas', 'Location: Check Canvas'), ('email', 'Location info shared via email')):
            with self.assertRaises(ValueError):
                semantic._check_location(name, text)
        semantic._check_location('Canvas', 'Join the online workshop on Canvas')
        result = copy.deepcopy(case['result'])
        result['occurrences'][0].update(location='', location_evidence=[])
        semantic.validate(semantic._attach_source_quotes(result, case['source']), case['source'])


class DuplicateTests(unittest.TestCase):
    def test_numbered_tryout_reminder_and_revised_speaker_merge(self):
        for name in ('volleyball', 'pse', 'pse_earlier'):
            a, b = CASES[name]
            with self.subTest(name=name):
                self.assertTrue(reconcile.same_event(a, b))
                self.assertTrue(reconcile.same_event(b, a))
                self.assertEqual(1, len(reconcile.plan([a, b], now=datetime(2026, 10, 3, tzinfo=timezone.utc))[1]))
                for changed in (b | {'host_handle': 'other'}, b | {'starts_at': '2026-10-07T04:00:00Z'},
                                b | {'title': 'Tryouts Day 2' if name == 'volleyball' else 'Guest Speaker #2'}):
                    self.assertFalse(reconcile.same_event(a, changed))
                reviews = reconcile.Reviews(distinct=frozenset({frozenset({a['id'], b['id']})}))
                self.assertEqual(([], set(), {}), reconcile.plan([a, b], reviews=reviews))

    def test_unannounced_venue_disagreement_still_requires_review(self):
        a, b = CASES['pse']
        self.assertFalse(reconcile.same_event(a, b | {'description': 'Come to our guest speaker and networking event.'}))


class FlyerStorageTests(unittest.TestCase):
    def test_oversize_image_fits_bucket_and_remains_decodable(self):
        from PIL import Image
        source = io.BytesIO()
        Image.new('RGB', (3000, 2000), 'navy').save(source, 'JPEG')
        # Extra JPEG metadata/trailing data must not reach the 5 MiB bucket.
        original = source.getvalue() + b'\0' * extraction.MAX_FLYER_BYTES
        bucket = MagicMock()
        bucket.get_public_url.return_value = 'https://storage.example/flyer.jpg'
        with patch('db.client') as client:
            client.return_value.storage.from_.return_value = bucket
            self.assertEqual('https://storage.example/flyer.jpg', extraction._upload_flyer(
                {'handle': 'club', 'media_id': '123'}, 'slide', original))
        uploaded = bucket.upload.call_args.args[1]
        self.assertLessEqual(len(uploaded), extraction.MAX_FLYER_BYTES)
        with Image.open(io.BytesIO(uploaded)) as decoded:
            self.assertEqual('JPEG', decoded.format)
            self.assertEqual((2560, 1707), decoded.size)

    def test_small_images_are_preserved_and_upload_failures_remain_retryable(self):
        record = {'handle': 'club', 'media_id': '123'}
        with patch('db.client') as client:
            bucket = client.return_value.storage.from_.return_value
            extraction._upload_flyer(record, 'slide', b'unchanged')
            self.assertEqual(b'unchanged', bucket.upload.call_args.args[1])
            bucket.upload.side_effect = RuntimeError('temporary storage outage')
            self.assertIsNone(extraction._upload_flyer(record, 'slide', b'unchanged'))


class ReviewedSourceTests(unittest.TestCase):
    def test_reviewed_flyers_validate_and_replay_without_model_calls(self):
        expected = {'asme': 1, 'snowclub': 1, 'hanwave': 1, 'tennis': 3, 'asucr': 5,
                    'bestbuddies': 5, 'rbrains': 5, 'sdrc': 10, 'msp': 1, 'hub': 4,
                    'leadership': 7, 'apec': 8}
        mapped = {}
        with tempfile.TemporaryDirectory() as cache, patch.object(publication, 'CACHE_DIR', Path(cache)), \
             patch.object(semantic, 'assess', side_effect=AssertionError('Unexpected model call')):
            for name, case in REVIEWS.items():
                source = case['source']
                effective = source | {'texts': source['texts'] | (case['ocr_corrections'] or {})}
                payload = publication.record_review(source, semantic._attach_source_quotes(
                    copy.deepcopy(case['result']), effective), reviewer='Regression: saved flyer audit',
                    ocr_corrections=case['ocr_corrections'])
                self.assertEqual(semantic.fingerprint(source), payload['source_hash'])
                self.assertEqual(source, payload['source'])
                publication._cache_path(source['source_key']).unlink()
                reused = publication.cached_assessment(source, payload)
                self.assertFalse(reused.produced_live)
                mapped[name] = publication.post_rows(case['record'], case['cached'], reused.payload, {}, '2026-10-03T07:00:00Z')[0]
                self.assertEqual(expected[name], len(mapped[name]), name)
        self.assertFalse(mapped['snowclub'][0]['has_free_food'])
        self.assertEqual('', mapped['msp'][0]['location'])
        self.assertTrue(all(r['has_free_food'] for r in mapped['leadership']))
        self.assertFalse(any(r['has_free_food'] for r in mapped['rbrains']))
        self.assertEqual({'student_event', 'student_deadline'}, {r['content_kind'] for r in mapped['tennis']})
        by_date = {}
        for row in mapped['sdrc']:
            local = datetime.fromisoformat(row['starts_at']).astimezone(semantic.PACIFIC)
            by_date.setdefault(local.date(), set()).add(local.hour)
        self.assertEqual(5, len(by_date))
        self.assertTrue(all(hours == {10, 15} for hours in by_date.values()))
        self.assertEqual('2026-12-02T02:30:00+00:00', next(r['starts_at'] for r in mapped['rbrains'] if r['title'] == 'Coffee & Cram'))
        for title, day in (('Step Up, Stand Out', 20), ('From Campus to the Capital', 22)):
            row = next(r for r in mapped['leadership'] if r['title'].startswith(title))
            self.assertEqual(day, datetime.fromisoformat(row['starts_at']).astimezone(semantic.PACIFIC).day)


if __name__ == '__main__':
    unittest.main()
