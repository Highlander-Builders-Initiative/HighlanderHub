"""Verified hpix 1.2.17 feed adapter and completion signals."""
import re

HPIX_KIND = {'GraphImage': 1, 'GraphVideo': 2, 'GraphSidecar': 8}


def hpix_item(row: dict) -> dict:
    """Map an hpix/instagram-scraper profile-feed node onto our contract.

    The actor returns raw Instagram GraphQL nodes. Absence of a field is an
    incomplete row, never an empty caption, carousel or coauthor list.
    """
    node = row.get('data')
    if not isinstance(node, dict):
        raise ValueError('no post node; profile retrieval failed')
    for field in ('__typename', 'id', 'shortcode', 'taken_at_timestamp', 'owner',
                  'coauthor_producers', 'edge_media_to_caption', 'display_resources'):
        if field not in node:
            raise ValueError(f'missing {field}')
    if node['__typename'] not in HPIX_KIND:
        raise ValueError(f"unsupported __typename {node['__typename']!r}")
    if node['__typename'] == 'GraphSidecar' and 'edge_sidecar_to_children' not in node:
        raise ValueError('missing edge_sidecar_to_children')
    if not isinstance(node['coauthor_producers'], list):
        raise ValueError('invalid coauthor_producers')

    def media(child):
        sources = [r for r in (child.get('display_resources') or [])
                   if isinstance(r.get('src'), str)]
        best = max(sources, key=lambda r: (r.get('config_width') or 0) * (r.get('config_height') or 0),
                   default=None)
        return {'media_type': 2 if child.get('is_video') else 1,
                'image_url': (best or {}).get('src') or child.get('display_url')}

    children = [edge['node'] for edge in
                ((node.get('edge_sidecar_to_children') or {}).get('edges') or [])]
    captions = [edge['node'].get('text')
                for edge in (node['edge_media_to_caption'].get('edges') or [])]
    owner = node['owner'] or {}
    return {**media(node), 'media_type': HPIX_KIND[node['__typename']],
            'id': node['id'], 'pk': node['id'], 'code': node['shortcode'],
            'scraped_username': row.get('input'), 'taken_at': node['taken_at_timestamp'],
            'user': {'username': owner.get('username'), 'pk': owner.get('id')},
            'coauthor_producers': node['coauthor_producers'] or [],
            'caption': {'text': captions[0] if captions else None},
            'carousel_media': [media(child) for child in children]}



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
