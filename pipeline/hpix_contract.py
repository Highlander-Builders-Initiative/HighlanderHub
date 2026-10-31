"""Verified hpix 1.2.25+ feed adapter and completion signals.

Since 1.2.25 each row's raw `data` is Instagram's v1 media object, the same
shape `normalize` already reads for individual-post lookups. hpix guarantees
only the mapped `metadata` block; raw `data` follows Meta's API and can change
without notice. We still need raw `data` for carousel slides and the exact
numeric media ID, so every row must agree with `metadata` on identity, time,
owner and caption, and a missing field or any disagreement fails the row closed.
"""
import re

from post_archive import parse_instant

RAW_FIELDS = ('id', 'pk', 'code', 'taken_at', 'user', 'media_type',
              'caption', 'coauthor_producers')
META_FIELDS = ('shortcode', 'taken_at', 'owner_id', 'owner_username', 'is_video')


def hpix_item(row: dict) -> dict:
    """Map an hpix/instagram-scraper feed row onto our native contract.

    Absence of a field is an incomplete row, never an empty caption, carousel
    or coauthor list.
    """
    node = row.get('data')
    if not isinstance(node, dict):
        raise ValueError('no post node; profile retrieval failed')
    meta = row.get('metadata')
    if not isinstance(meta, dict):
        raise ValueError('missing metadata')
    for field in RAW_FIELDS:
        if field not in node:
            raise ValueError(f'missing {field}')
    for field in META_FIELDS:
        if field not in meta:
            raise ValueError(f'missing metadata.{field}')
    # hpix leaves metadata.caption out for a post with no caption; raw data
    # then says so explicitly with a null caption.
    if 'caption' not in meta and node['caption'] is not None:
        raise ValueError('missing metadata.caption')
    if node['media_type'] not in (1, 2, 8):
        raise ValueError(f"unsupported media_type {node['media_type']!r}")
    if node['media_type'] == 8 and not isinstance(node.get('carousel_media'), list):
        raise ValueError('missing carousel_media')
    if not isinstance(node['coauthor_producers'], list):
        raise ValueError('invalid coauthor_producers')

    owner = node['user'] if isinstance(node['user'], dict) else {}
    caption = node['caption']
    text = caption.get('text') if isinstance(caption, dict) else caption
    posted = parse_instant(meta['taken_at'])
    agrees = {
        'shortcode': node['code'] == meta['shortcode'],
        'media id': str(node['id']).split('_')[0] == str(node['pk']),
        'taken_at': (posted is not None and isinstance(node['taken_at'], (int, float))
                     and not isinstance(node['taken_at'], bool)
                     and abs(posted.timestamp() - node['taken_at']) < 1),
        'owner': (str(owner.get('pk') or owner.get('id')) == str(meta['owner_id'])
                  and str(owner.get('username') or '').lower() == str(meta['owner_username'] or '').lower()),
        'caption': (text or '') == (meta.get('caption') or ''),
        'is_video': (node['media_type'] == 2) == bool(meta['is_video']),
    }
    disagree = [name for name, ok in agrees.items() if not ok]
    if disagree:
        raise ValueError('raw data disagrees with metadata: ' + ', '.join(disagree))
    return {**node, 'scraped_username': row.get('input')}


def capped_profiles(text: str) -> set[str]:
    # N counts emitted posts, not every node visited before shouldSkip. This
    # catches visible caps but can miss a truncated walk after heavy skipping;
    # a low N alone cannot establish exhaustive historical/backfill coverage.
    return {handle.lower() for handle, count, limit in re.findall(
        r"\[([A-Za-z0-9_.]+)\] Scraped (\d+)/(\d+) posts", text)
        if int(count) >= int(limit)}


def completed_profiles(text: str) -> set[str]:
    finished = set(re.findall(r"INFO\s+Crawler: \[([A-Za-z0-9_.]+)\] Finished scraping posts", text))
    failed = set(re.findall(r"Failed to scrape profile ([A-Za-z0-9_.]+)\. The account may be private or restricted", text))
    return {handle.lower() for handle in finished} - {handle.lower() for handle in failed} - capped_profiles(text)
