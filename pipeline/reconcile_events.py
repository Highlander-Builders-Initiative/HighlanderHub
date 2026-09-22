"""Reconcile corroborated duplicates across the independently published sources.

Run after imports (even partially failed ones). Canonical updates are saved
before unlocked duplicates are removed. Dry-run planning is pure; locked and
admin-deleted identities constrain the whole corroborated group.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from event_identity import _parse_instant, _row_score, event_key
from event_dates import PACIFIC_TZ

log = logging.getLogger("pipeline.reconcile_events")
_GENERIC_WORDS = frozenset("first second third general body meeting club weekly monthly annual fall winter spring summer welcome back workshop session orientation open house social event ucr uc riverside university california of at the and for to a an".split())
_TITLE_NOISE = frozenset("the of at and for to a an annual save date".split())
_TITLE_QUALIFIERS = frozenset("network celebration ucr uc riverside university california".split())
_SHORTCODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
_FEED_PERMALINK = re.compile(r"https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]{1,11})/?(?:[?#]|$)")
# Current rows end in _p<media_id>; retired story reshares were keyed on the
# original post as ig_post_<media_id>_<minute>.
_MEDIA_ID = re.compile(r"ig_post_(\d+)_\d{8}T\d{4}Z|ig_.+_p(\d+)")
_MENTION = re.compile(r"@([a-z0-9._]+)")


def _source_media(row: dict) -> set[str]:
    """Instagram post IDs a row was published from, by ID or feed permalink."""
    media = set()
    if match := _MEDIA_ID.fullmatch(str(row.get("id") or "")):
        media.add(match.group(1) or match.group(2))
    if match := _FEED_PERMALINK.match(str(row.get("source_url") or "")):
        value = 0
        for char in match.group(1):
            value = value * 64 + _SHORTCODE_ALPHABET.index(char)
        media.add(str(value))
    return media


def _credits(row: dict, other: dict) -> bool:
    """Whether row's caption tags the account that published other."""
    handle = str(other.get("host_handle") or "").casefold()
    mentions = {m.rstrip(".") for m in _MENTION.findall(str(row.get("description") or "").casefold())}
    return bool(handle) and handle in mentions


def _title_words(row: dict) -> set[str]:
    return {'celebration' if w == 'gala' else w
            for w in re.findall(r"[a-z0-9]+", str(row.get("title") or "").casefold())
            if w not in _TITLE_NOISE}


def _same_place(left: dict, right: dict) -> bool:
    noise = {'the', 'and', 'at', 'of', 'ucr', 'uc', 'riverside', 'university', 'california'}
    locations = [set(re.findall(r"[a-z]+|[0-9]+", str(r.get('location') or '').casefold())) - noise
                 for r in (left, right)]
    return min(map(len, locations)) >= 2 and (locations[0] <= locations[1] or locations[1] <= locations[0])


def _unspecified_place(row: dict) -> bool:
    location = ' '.join(re.findall(r'[a-z0-9]+', str(row.get('location') or '').casefold()))
    return location in {'', 'ucr', 'uc riverside', 'university of california riverside',
                        'ucr campus', 'uc riverside campus'}


def _same_teaser_title(left: dict, right: dict) -> bool:
    words = [_title_words(row) for row in (left, right)]
    editions = [set(re.findall(r'\b(\d+(?:st|nd|rd|th))\s+annual\b',
                              str(row.get('title') or '').casefold())) for row in (left, right)]
    # "3rd Annual Tea Talk" and "Tea Talk" can name the same event. Two
    # explicit editions, or ordinary numbered sessions, must still agree.
    if bool(editions[0]) != bool(editions[1]):
        words = [tokens - edition for tokens, edition in zip(words, editions)]
    return words[0] == words[1]


def _date_only(row: dict) -> bool:
    # Never infer missing time from midnight alone (real midnight events exist).
    start, end = _parse_instant(row.get('starts_at')), _parse_instant(row.get('ends_at'))
    return bool(row.get('all_day') is True and start and end and end > start
                and start.astimezone(PACIFIC_TZ).time().isoformat() == '00:00:00'
                and (end.astimezone(PACIFIC_TZ).date() - start.astimezone(PACIFIC_TZ).date()).days <= 1)


def _merged_hosts(winner: dict, rows: list[dict]) -> list[dict]:
    from instagram_rows import _ANONYMIZED_HOST_HANDLES
    hosts = {}
    for row in [winner, *rows]:
        for host in [{'host': row.get('host') or '', 'host_handle': row.get('host_handle')},
                     *(row.get('hosts') or [])]:
            handle = str(host.get('host_handle') or '').strip().lstrip('@').casefold()
            if not handle or handle in _ANONYMIZED_HOST_HANDLES:
                continue
            hosts.setdefault(handle, {'host': host.get('host') or handle, 'host_handle': handle})
    return list(hosts.values())


def _rsvp_identity(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path.rstrip("/") == "":
        return None
    query = [(k, v) for k, v in parse_qsl(parsed.query) if k != "fbclid" and not k.startswith("utm_")]
    return urlunsplit((parsed.scheme, parsed.netloc.casefold(), parsed.path.rstrip("/"), urlencode(sorted(query)), ""))


def same_event(left: dict, right: dict) -> bool:
    """Match corroborated announcements, allowing an explicit date-only teaser."""
    start = _parse_instant(left.get("starts_at"))
    other_start = _parse_instant(right.get('starts_at'))
    if start is None or other_start is None:
        return False
    if left.get('content_kind') != right.get('content_kind'):
        return False
    if start != other_start:
        if (start.astimezone(PACIFIC_TZ).date() != other_start.astimezone(PACIFIC_TZ).date()
                or _date_only(left) == _date_only(right)):
            return False
        a, b = _title_words(left), _title_words(right)
        distinctive = (a & b) - _GENERIC_WORDS - {'celebration', 'anniversary'}
        same_host = any(left.get(k) and str(left[k]).casefold() == str(right.get(k) or '').casefold()
                        for k in ('host', 'host_handle'))
        teaser, timed = (left, right) if _date_only(left) else (right, left)
        same_account = (bool(left.get('host_handle')) and
                        str(left['host_handle']).strip().lstrip('@').casefold() ==
                        str(right.get('host_handle') or '').strip().lstrip('@').casefold())
        # An explicit save-the-date may omit the room that its own account
        # announces later. Missing venue detail is not a conflicting venue.
        venue_pending = (same_account and _unspecified_place(teaser) and not _unspecified_place(timed)
                         and re.search(r'\bsave\s+the\s+date\b', str(teaser.get('description') or ''), re.I)
                         and len(distinctive) >= 2)
        # A date-only campaign cannot absorb a merely related timed activity.
        # Require a specific common title and ownership/signup evidence.
        rsvp = _rsvp_identity(left.get('rsvp_url'))
        return bool(len(a & b) >= 3 and distinctive and _same_teaser_title(left, right)
                    and (_same_place(left, right) or venue_pending)
                    and (same_host or _credits(left, right) or _credits(right, left)
                         or (rsvp and rsvp == _rsvp_identity(right.get('rsvp_url')))))
    if event_key(left) is not None and event_key(left) == event_key(right):
        return True
    # A post publishes exactly one event, so one post at one instant is one event
    # however differently a feed row and a story reshare of it were titled.
    if _source_media(left) & _source_media(right):
        return True
    a, b = _title_words(left), _title_words(right)
    common = a & b
    rsvp = _rsvp_identity(left.get("rsvp_url"))
    if rsvp and rsvp == _rsvp_identity(right.get("rsvp_url")) and len(common) >= 2:
        return True
    # Generic meeting titles never establish common ownership across accounts.
    if len(common - _GENERIC_WORDS) < 2:
        return False
    # A partner's promotion tags the organizer's account; its title and place
    # are paraphrases, but the event cannot end at a different time.
    ends = {_parse_instant(r.get("ends_at")) for r in (left, right)} - {None}
    if (_credits(left, right) or _credits(right, left)) and len(ends) <= 1:
        return True
    # Split room codes so "LOFT 84" and "LOFT84" name the same place.
    same_place = _same_place(left, right)
    same_host = any(left.get(k) and str(left[k]).casefold() == str(right.get(k) or '').casefold()
                    for k in ('host', 'host_handle'))
    return (same_place or same_host) and (a <= b or b <= a) and (a ^ b) <= _TITLE_QUALIFIERS


def plan(rows: list[dict], tombstones: list[dict] = (), *, now: datetime | None = None) -> tuple[list[dict], set[str]]:
    """Return changed canonical rows and removable IDs; do not mutate inputs."""
    groups: list[list[dict]] = []
    blocked = {r["id"] for r in tombstones}
    by_id = {r["id"]: r for r in rows}
    candidates = [*rows, *(r for r in tombstones if r['id'] not in by_id)]
    # A teaser for two different timed sessions does not identify either one.
    ambiguous = {row['id'] for row in candidates if _date_only(row) and len({
        _parse_instant(other.get('starts_at')) for other in candidates
        if not _date_only(other) and same_event(row, other)
    }) > 1}
    def matches_pair(left, right):
        if ({left['id'], right['id']} & ambiguous
                and _parse_instant(left.get('starts_at')) != _parse_instant(right.get('starts_at'))):
            return False
        return same_event(left, right)
    for row in sorted(candidates, key=lambda r:r['id']):
        matches = [g for g in groups if any(matches_pair(row, other) for other in g)]
        # Two related date-only teasers must not bridge incompatible sessions.
        timed_starts = {_parse_instant(r.get('starts_at'))
                        for r in [row, *(r for group in matches for r in group)]
                        if not _date_only(r)}
        if len(timed_starts) > 1:
            matches = []
        if matches:
            first = matches[0]
            first.append(row)
            for group in matches[1:]:
                first.extend(group)
                groups.remove(group)
        else:
            groups.append([row])
    updates, removed = [], set()
    for group in groups:
        live = [r for r in group if r['id'] in by_id]
        if any(r['id'] in blocked for r in group):
            removed.update(r['id'] for r in live if not r.get('is_locked'))
            continue
        if len(live) < 2:
            continue
        if now and all((_parse_instant(r.get('ends_at') or r.get('starts_at')) or now) < now for r in live):
            continue
        winner = max(live, key=lambda r: (bool(r.get('is_locked')), not _date_only(r), r.get('source') != 'instagram', _row_score(r)))
        removed.update(r['id'] for r in live if r['id'] != winner['id'] and not r.get('is_locked'))
        if winner.get('is_locked'):
            continue
        merged = dict(winner)
        merged['has_free_food'] = any(r.get('has_free_food') for r in live)
        hosts = _merged_hosts(winner, live)
        if len(hosts) > 1 or winner.get('hosts'):
            merged['hosts'] = hosts
        for key in ('ends_at', 'rsvp_url', 'image_url'):
            if not merged.get(key):
                options = {r[key] for r in live if r.get(key)
                           and not (key == 'ends_at' and _date_only(r) and not _date_only(winner))}
                if len(options) == 1:
                    merged[key] = options.pop()
        # Date-only weekend announcements often omit the end on the campus
        # listing. The corrected flyers supply the complete final day.
        start = _parse_instant(winner.get('starts_at'))
        if start and start.astimezone(PACIFIC_TZ).time().isoformat() == '00:00:00':
            ends = [_parse_instant(r.get('ends_at')) for r in live]
            ends = [e for e in ends if e and e > start and e.astimezone(PACIFIC_TZ).time().isoformat() in {'00:00:00', '23:59:59'}]
            if ends:
                merged['ends_at'] = max(ends).isoformat()
        if merged != winner:
            updates.append(merged)
    return updates, removed


def _tombstoned_candidates(deleted: set[str]) -> list[dict]:
    """Rebuild deleted source identities so a different source cannot revive them."""
    if not deleted:
        return []
    from config import load_account_meta
    import assessed_events as publication
    registry = publication.load_registry()
    now = datetime.now(timezone.utc).isoformat()
    meta = load_account_meta()
    tombstones = []

    def assessed_candidates(key: str, raw: dict, cached: dict) -> None:
        record = registry.get(key)
        if record is None:
            return
        # Errors preserve publication's last successful assessment. Never run
        # a new model assessment while reconstructing an admin deletion.
        payload = record.get('last_complete_assessment') or record.get('assessment') or {}
        if payload.get('status') != 'complete' or 'result' not in payload:
            return
        rows, aliases = publication.post_rows(raw, cached or {}, payload, meta, now)
        identities = aliases | set(record.get('event_ids', [])) | set(record.get('known_event_ids', []))
        identities.update(row['id'] for row in rows)
        # Match the publication RPC: an override on any known source identity
        # constrains its replacements, including fanout and remapped IDs.
        if deleted & identities:
            tombstones.extend(rows)

    # Posts have no pre-assessment identity to fall back on, so an unregistered
    # post simply contributes nothing here.
    import extract_posts as igposts
    import post_archive
    for record in post_archive.iter_local_posts():
        path = igposts._cache_path(str(record.get('media_id')))
        if path.exists():
            assessed_candidates(f"instagram:post:{record['media_id']}", record,
                                igposts._read_json(path))
    return tombstones


def _inherit_notifications(rows: list[dict], updates: list[dict], removed: set[str]) -> None:
    """Keep a sent alert attached to the surviving event without sending again."""
    from db import client
    from discord_notify import free_food_notification_key
    survivors = {r['id']:r for r in rows if r['id'] not in removed}
    survivors.update({r['id']:r for r in updates})
    replacements: dict[str, list[dict]] = {}
    for row in rows:
        if row['id'] not in removed:
            continue
        matches = [other for other in survivors.values() if same_event(row, other)]
        if len(matches) == 1:
            replacements.setdefault(matches[0]['id'], []).append(row)
    if not replacements:
        return
    ids = sorted(set(replacements) | {r['id'] for group in replacements.values() for r in group})
    ledger = []
    for offset in range(0, len(ids), 200):
        ledger.extend(client().table('discord_notifications').select('*').eq('kind', 'free_food').in_('event_id', ids[offset:offset+200]).execute().data or [])
    by_id = {n['event_id']:n for n in ledger}
    aliases = []
    for canonical_id, siblings in replacements.items():
        sent = [by_id[r['id']] for r in siblings if r['id'] in by_id]
        if not sent or canonical_id in by_id:
            continue
        aliases.append({
            'event_id':canonical_id, 'kind':'free_food',
            'notification_key':free_food_notification_key(survivors[canonical_id]),
            'notified_at':min(n['notified_at'] for n in sent),
        })
    if aliases:
        # A matching title/day key already protects both IDs; keep that record.
        client().table('discord_notifications').upsert(
            aliases, on_conflict='kind,notification_key', ignore_duplicates=True,
        ).execute()


def main(*, notify: bool = True) -> None:
    from db import client, get_deleted_event_ids, get_imported_events
    from discord_notify import notify_free_food_events
    rows = get_imported_events()
    updates, removed = plan(rows, _tombstoned_candidates(get_deleted_event_ids()), now=datetime.now(timezone.utc))
    original = {row['id']: row for row in rows}
    for row in updates:
        before = original[row['id']]
        changes = {key: value for key, value in row.items() if value != before.get(key)}
        query = client().table('events').update(changes).eq('id', row['id']).eq('is_locked', False)
        if before.get('updated_at'):
            query = query.eq('updated_at', before['updated_at'])
        if len(query.execute().data or []) != 1:
            raise RuntimeError(f"Canonical event changed during reconciliation: {row['id']}")
    _inherit_notifications(rows, updates, removed)
    removals = []
    for event_id in sorted(removed):
        matches = [r for r in rows if r['id'] not in removed and same_event(original[event_id], r)]
        removals.append({
            'id': event_id,
            'replacement_id': matches[0]['id'] if len(matches) == 1 else None,
            'updated_at': original[event_id].get('updated_at'),
        })
    deleted = client().rpc('remap_assessed_event_sources', {'removals': removals}).execute().data if removals else 0
    log.info('Reconciled %d canonical updates and %d duplicate/deleted rows', len(updates), deleted)
    if notify:
        canonical = {r['id']:r for r in rows if r['id'] not in removed}
        canonical.update({r['id']:r for r in updates})
        sent = notify_free_food_events(canonical.values())
        log.info('Sent %d free food Discord notifications', sent)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
