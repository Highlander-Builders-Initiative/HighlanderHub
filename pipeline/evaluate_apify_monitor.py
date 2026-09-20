"""Offline comparison of saved candidate datasets against a trusted reference.

Never starts actors, writes checkpoints or approves a production migration.
Reference recall measures agreement with that snapshot, not absolute Instagram
recall. A successful preview fetch is not proof of pagination to the cutoff;
only a provider that logs the older-than-cutoff post it stopped at proves that,
and only for the profiles it named.

Candidate formats: `snuggly` (snuggly_beanie_970 monitor 0.1.7) and `hpix`
(hpix/instagram-scraper profile feeds). Reference formats: `official`
(apify/instagram-post-scraper rows) and `archive` (records this pipeline
already wrote to data/posts, which the production collector produced).
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from apify_posts import normalize, official_item, profile_handle
from post_archive import parse_instant
from hpix_contract import hpix_item


def monitor_item(row: dict) -> dict:
    """Experimental mapping used only by this evaluator, not ingestion."""
    # Absence cannot be interpreted as an empty caption/carousel/coauthor list.
    for field in ('caption', 'children', 'coauthors', 'owner'):
        if field not in row:
            raise ValueError(f'missing {field}')
    if not isinstance(row['children'], list) or not isinstance(row['coauthors'], list):
        raise ValueError('invalid children/coauthors')
    kinds = {'image': 1, 'video': 2, 'carousel': 8}
    def media(node):
        if node.get('postType') not in kinds:
            raise ValueError('missing or unsupported postType')
        return {'media_type': kinds.get(node.get('postType')),
                'image_url': node.get('displayUrl')}
    timestamp = parse_instant(row.get('publishedAt'))
    return {**media(row), 'id': row.get('postId'), 'code': row.get('shortcode'),
            'scraped_username': row.get('username'),
            'taken_at': timestamp.timestamp() if timestamp else None,
            'user': row['owner'], 'coauthor_producers': row['coauthors'],
            'caption': {'text': row['caption']},
            'carousel_media': [media(child) for child in row['children']]}



def snuggly_rows(candidate):
    for row in candidate:
        if row.get('recordType') == 'post':
            yield row.get('username'), row.get('shortcode'), row


def snuggly_coverage(log, profiles, candidate=(), cutoff=None):
    """A preview fetch line, which is not proof of a scan to the cutoff."""
    fetched, unavailable, scanned = {}, set(), set()
    for handle, count in re.findall(r'INFO\s+([\w.]+): profile=(?:true|false), posts=(\d+), source=', log):
        if handle in profiles:
            fetched[handle] = int(count)
    for handle in re.findall(r'WARN\s+([\w.]+): profile unavailable;', log):
        if handle in profiles:
            unavailable.add(handle)
    return fetched, unavailable, scanned


def hpix_rows(candidate):
    for row in candidate:
        if row.get('kind') in ('post', 'reel'):
            yield row.get('input'), (row.get('data') or {}).get('shortcode'), row


def hpix_coverage(log, profiles, candidate=(), cutoff=None):
    """Only an explicit finish, with no failure row, may advance a checkpoint.

    `Stopping at post X (taken at D)` names the older-than-cutoff post that
    ended the walk, so D < cutoff is per-profile evidence of pagination. A
    `profile` row carrying a null body is the actor's retrieval-failure marker
    and outranks any finish line, exactly as `no_items` does for the official
    build.
    """
    fetched, unavailable, scanned = {}, set(), set()
    for handle, count, _ in re.findall(r'\[([\w.]+)\] Scraped (\d+)/(\d+) posts', log):
        if handle in profiles:
            fetched[handle] = int(count)
    for handle in re.findall(r'\[([\w.]+)\] Finished scraping posts', log):
        if handle in profiles:
            fetched.setdefault(handle, 0)
    for handle, stopped_at in re.findall(
            r'\[([\w.]+)\] Stopping at post \S+ \(taken at ([\dT:.Z+-]+)\)', log):
        moment = parse_instant(stopped_at)
        if handle in profiles and cutoff is not None and moment is not None and moment < cutoff:
            scanned.add(handle)
    for handle in re.findall(
            r'Failed to scrape profile ([\w.]+)\. The account may be private or restricted', log):
        if handle in profiles:
            unavailable.add(handle)
    for row in candidate:
        if row.get('kind') == 'profile' and row.get('data') is None:
            handle = row.get('input')
            if handle in profiles:
                unavailable.add(handle)
    return fetched, {h for h in unavailable}, scanned - unavailable


CANDIDATES = {'snuggly': (snuggly_rows, monitor_item, snuggly_coverage),
              'hpix': (hpix_rows, hpix_item, hpix_coverage)}


def official_rows(reference, profiles, start):
    for row in reference:
        if row.get('error'):
            continue
        handle = profile_handle(row.get('inputUrl', ''))
        if handle not in profiles or parse_instant(row['timestamp']) < start:
            continue
        yield handle, row, official_item(row)


def archive_rows(reference, profiles, start):
    """Records this pipeline already wrote; they are normalized, not raw."""
    for row in reference:
        handle = (row.get('handle') or '').lower()
        posted = parse_instant(row.get('posted_at'))
        if handle not in profiles or posted is None or posted < start:
            continue
        yield handle, row, None


REFERENCES = {'official': official_rows, 'archive': archive_rows}


def fraction(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'rate': numerator / denominator if denominator else None}


def evaluate(reference, candidate, log, profiles, cutoff, seen=(),
             candidate_format='snuggly', reference_format='official'):
    start = parse_instant(cutoff)
    if start is None:
        raise ValueError('invalid cutoff')
    if candidate_format not in CANDIDATES or reference_format not in REFERENCES:
        raise ValueError('unknown candidate/reference format')
    rows_of, item_of, coverage_of = CANDIDATES[candidate_format]
    profiles = set(profiles)
    seen = set(seen)
    accounts = {h: {'handle': h} for h in profiles}
    now = datetime.now(timezone.utc)
    expected, observed, excluded = {}, {}, []
    failures = []
    # Reference rows must satisfy actual roster ownership, not mere feed presence.
    for handle, raw, mapped in REFERENCES[reference_format](reference, profiles, start):
        try:
            record = raw if mapped is None else normalize(mapped, accounts, now)
            if record['shortcode'] in seen:
                continue
            expected[handle, record['shortcode']] = (raw if mapped is not None else None, record)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            excluded.append({'shortcode': raw.get('shortCode') or raw.get('shortcode'),
                             'reason': str(exc)})
    emitted = []
    for handle, shortcode, row in rows_of(candidate):
        if handle not in profiles:
            continue
        emitted.append(shortcode)
        try:
            record = normalize(item_of(row), accounts, now)
            if parse_instant(record['posted_at']) >= start:
                observed[record['handle'], record['shortcode']] = (row, record)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            failures.append({'shortcode': shortcode, 'reason': str(exc)})
    fetched, unavailable, scanned = coverage_of(log, profiles, candidate, start)
    matched = expected.keys() & observed.keys()
    fidelity = {field: [] for field in ('id', 'owner', 'type', 'timestamp', 'caption', 'carousel', 'coauthors')}
    mismatches = []
    for key in sorted(matched):
        baseline, a = expected[key]
        raw, b = observed[key]
        checks = {'id': a['media_id'] == b['media_id'],
                  'owner': (a['owner_username'], str(a['owner_userid'])) ==
                           (b['owner_username'], str(b['owner_userid'])),
                  'type': a['typename'] == b['typename'],
                  'timestamp': a['posted_at'] == b['posted_at'],
                  'caption': a['caption'] == b['caption']}
        if baseline is not None and baseline.get('type') == 'Sidecar':
            ids = [str(c.get('id') or '') for c in baseline['childPosts']]
            other = [str(c.get('id') or c.get('postId') or '') for c in (raw.get('children') or [])]
            checks['carousel'] = bool(ids) and all(ids) and ids == other
        elif a['typename'] == 'GraphSidecar':
            # media_key survives re-signed CDN URLs, so ordered keys compare.
            keys = [m['media_key'] for m in a['media']]
            checks['carousel'] = bool(keys) and all(keys) and keys == [m['media_key'] for m in b['media']]
        if baseline is not None:
            authors = {(str(c.get('id')), c.get('username')) for c in baseline.get('coauthorProducers', [])}
            if authors:
                checks['coauthors'] = authors == {(str(c.get('id')), c.get('username'))
                                                  for c in (raw.get('coauthors') or [])}
        for field, passed in checks.items():
            fidelity[field].append(passed)
            if not passed:
                mismatches.append({'profile': key[0], 'shortcode': key[1], 'field': field})
    rows = []
    for h in sorted(profiles):
        wanted = {code for handle, code in expected if handle == h}
        got = {code for handle, code in observed if handle == h}
        rows.append({'profile': h, 'preview_fetched': h in fetched,
                     'unavailable': h in unavailable,
                     # Only this may advance a checkpoint: an explicit scan past
                     # the cutoff with no retrieval failure recorded anywhere.
                     'scan_completed': h in scanned,
                     'reference_posts': len(wanted), 'matched_posts': len(wanted & got),
                     'missing_shortcodes': sorted(wanted - got),
                     'false_quiet': bool(wanted) and fetched.get(h) == 0 and h not in unavailable})
    active = [r for r in rows if r['reference_posts']]
    return {'reference_recall': fraction(len(matched), len(expected)),
            'preview_success': fraction(len(fetched.keys() - unavailable), len(profiles)),
            'scan_completed': fraction(sum(r['scan_completed'] for r in rows), len(profiles)),
            'retrieval_failures': sorted(unavailable),
            'false_quiet': fraction(sum(r['false_quiet'] for r in rows), len(active)),
            'contract_valid_rows': fraction(len(emitted) - len(failures), len(emitted)),
            'seen_shortcode_exports': sum(code in seen for code in emitted),
            'duplicate_exports_within_run': len(emitted) - len(set(emitted)),
            'fidelity': {k: fraction(sum(v), len(v)) for k, v in fidelity.items()},
            'profiles': rows, 'contract_failures': failures, 'mismatches': mismatches,
            'excluded_reference_rows': excluded,
            'pagination_to_cutoff_verified': bool(active) and all(r['scan_completed'] for r in active),
            'unmeasured': ['posting-to-discovery latency', 'absolute Instagram recall',
                           'incremental cost for one controlled new post'],
            'production_approved': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--profiles', nargs='+', required=True)
    parser.add_argument('--cutoff', required=True)
    parser.add_argument('--seen', type=Path, help='JSON array of shortcodes supplied to this run')
    parser.add_argument('--candidate-format', choices=sorted(CANDIDATES), default='snuggly')
    parser.add_argument('--reference-format', choices=sorted(REFERENCES), default='official')
    args = parser.parse_args()
    report = evaluate(json.loads(args.reference.read_text()), json.loads(args.candidate.read_text()),
                      args.log.read_text(), args.profiles, args.cutoff,
                      json.loads(args.seen.read_text()) if args.seen else (),
                      candidate_format=args.candidate_format,
                      reference_format=args.reference_format)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
