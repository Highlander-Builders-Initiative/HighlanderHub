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

log = logging.getLogger("pipeline.reconcile_events")
_GENERIC_WORDS = frozenset("first second third general body meeting club weekly monthly annual fall winter spring summer welcome back workshop session orientation open house social event ucr uc riverside university california of at the and for to a an".split())
_TITLE_NOISE = frozenset("the of at and for to a an annual save date".split())
_TITLE_QUALIFIERS = frozenset("network celebration ucr uc riverside university california".split())


def _title_words(row: dict) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", str(row.get("title") or "").casefold())
            if w not in _TITLE_NOISE and not re.fullmatch(r"\d+(?:st|nd|rd|th)?", w)}


def _rsvp_identity(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path.rstrip("/") == "":
        return None
    query = [(k, v) for k, v in parse_qsl(parsed.query) if k != "fbclid" and not k.startswith("utm_")]
    return urlunsplit((parsed.scheme, parsed.netloc.casefold(), parsed.path.rstrip("/"), urlencode(sorted(query)), ""))


def same_event(left: dict, right: dict) -> bool:
    """Require the same instant plus a distinctive title or shared signup link."""
    start = _parse_instant(left.get("starts_at"))
    if start is None or start != _parse_instant(right.get("starts_at")):
        return False
    if event_key(left) is not None and event_key(left) == event_key(right):
        return True
    a, b = _title_words(left), _title_words(right)
    common = a & b
    rsvp = _rsvp_identity(left.get("rsvp_url"))
    if rsvp and rsvp == _rsvp_identity(right.get("rsvp_url")) and len(common) >= 2:
        return True
    # Generic meeting titles never establish common ownership across accounts.
    if len(common) < 3 or len(common - _GENERIC_WORDS) < 2:
        return False
    locations = [set(re.findall(r"[a-z0-9]+", str(r.get('location') or '').casefold())) for r in (left, right)]
    same_place = bool(min(map(len, locations)) >= 2 and (locations[0] <= locations[1] or locations[1] <= locations[0]))
    same_host = bool(left.get('host') and str(left['host']).casefold() == str(right.get('host') or '').casefold())
    return (same_place or same_host) and (a <= b or b <= a) and (a ^ b) <= _TITLE_QUALIFIERS


def plan(rows: list[dict], tombstones: list[dict] = (), *, now: datetime | None = None) -> tuple[list[dict], set[str]]:
    """Return changed canonical rows and removable IDs; do not mutate inputs."""
    groups: list[list[dict]] = []
    blocked = {r["id"] for r in tombstones}
    by_id = {r["id"]: r for r in rows}
    for row in sorted([*rows, *(r for r in tombstones if r['id'] not in by_id)], key=lambda r:r['id']):
        matches = [g for g in groups if any(same_event(row, other) for other in g)]
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
        winner = max(live, key=lambda r: (bool(r.get('is_locked')), r.get('source') != 'instagram', _row_score(r)))
        removed.update(r['id'] for r in live if r['id'] != winner['id'] and not r.get('is_locked'))
        if winner.get('is_locked'):
            continue
        merged = dict(winner)
        merged['has_free_food'] = any(r.get('has_free_food') for r in live)
        for key in ('ends_at', 'rsvp_url', 'image_url'):
            if not merged.get(key):
                options = {r[key] for r in live if r.get(key)}
                if len(options) == 1:
                    merged[key] = options.pop()
        # Date-only weekend announcements often omit the end on the campus
        # listing. The corrected flyers supply the complete final day.
        start = _parse_instant(winner.get('starts_at'))
        from story_dates import PACIFIC_TZ
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
    import extract_stories as ig
    import normalize_events as structured
    now = datetime.now(timezone.utc).isoformat()
    meta = ig._load_account_meta()
    pairs = []
    for raw in ig._iter_raw_stories(set(meta)):
        path = ig._cache_path(str(raw.get('id')))
        if path.exists():
            pairs.append((raw, ig._read_json(path)))
    rows, _, retired_by = ig._collect_event_rows(pairs, meta, now)
    blocked = ig._inherit_tombstones(deleted, retired_by)
    for raw in structured._collect_raw(structured.UCR_EVENTS_RAW):
        rows.extend(structured._to_event_rows(raw, now))
    for raw in structured._collect_raw(structured.HIGHLANDER_LINK_RAW):
        row = structured._to_event_row_hlink(raw, now)
        if row:
            rows.append(row)
    return [r for r in rows if r['id'] in blocked]


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
