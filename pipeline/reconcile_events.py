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

from event_identity import _parse_instant, _row_score, event_key, imported_row_kind
from event_dates import PACIFIC_TZ

log = logging.getLogger("pipeline.reconcile_events")
_GENERIC_WORDS = frozenset("first second third general body meeting club weekly monthly annual fall winter spring summer welcome back workshop session orientation open house social event ucr uc riverside university california of at the and for to a an".split())
_TITLE_NOISE = frozenset("the of at and for to a an annual save date".split())
_TITLE_QUALIFIERS = frozenset("network celebration ucr uc riverside university california".split())
_EVENT_NOUNS = frozenset("conference fair celebration party reception".split())
# Words that name how a work is presented, not which work: "Joel Mejia Smith:
# It's been a while" and "Joel Mejia Smith performance: It's been a while".
_PRESENTATION_WORDS = frozenset("performance performances screening film live concert recital".split())
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
    handle = _account(other)
    mentions = {m.rstrip(".") for m in _MENTION.findall(str(row.get("description") or "").casefold())}
    return bool(handle) and handle in mentions


def _account(row: dict) -> str:
    return str(row.get('host_handle') or '').strip().lstrip('@').casefold()


def _same_account(left: dict, right: dict) -> bool:
    return bool(_account(left)) and _account(left) == _account(right)


def _same_host(left: dict, right: dict) -> bool:
    if _account(left) and _account(right):
        return _same_account(left, right)
    names = [str(r.get('host') or '').strip().casefold() for r in (left, right)]
    return bool(names[0]) and names[0] == names[1]


def _place_words(row: dict) -> set[str]:
    # City and state suffixes: "Culver Center of the Arts, Riverside, CA" and
    # "..., Downtown Riverside" name the same venue.
    noise = {'the', 'and', 'at', 'of', 'ucr', 'uc', 'riverside', 'university', 'california', 'campus',
             'ca', 'downtown', 'usa'}
    return set(re.findall(r'[a-z]+|[0-9]+', str(row.get('location') or '').casefold())) - noise


def _same_place(left: dict, right: dict) -> str:
    """Relate specific venues, including one-word names such as The Barn."""
    a, b = _place_words(left), _place_words(right)
    if not a or not b:
        return 'missing'
    if a <= b or b <= a:
        return 'same'
    # An organizer's center name omits its street/room detail. Only treat it
    # as unspecified for repeat titles from that same account; an actual room
    # qualifier ("MESC 112") must still conflict with a different room.
    if (_same_account(left, right)
            and _title_form(left, right)[0] == _title_form(right, left)[0]
            and (_host_venue(left) or _host_venue(right))):
        return 'missing'
    return 'conflicting'


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
            handle = _account(host)
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


def _host_aliases(row: dict) -> list[list[str]]:
    host = str(row.get('host') or '').casefold()
    # Parenthesized acronyms (ASPB) and leading full names (Alpha Epsilon
    # Pi) are supported by host metadata, not a global stopword list.
    full = re.findall(r'[a-z0-9]+', host)
    aliases = [full]
    campus = {'ucr', 'uc', 'riverside', 'university', 'california', 'at'}
    trimmed = [word for word in full if word not in campus]
    if trimmed != full:
        aliases.append(trimmed)
    aliases.extend(re.findall(r'[a-z0-9]+', value) for value in re.findall(r'\(([^)]+)\)', host))
    # Initials alone are not evidence of an alias. Require the account itself
    # to use those initials (POP + UCR, MESC + UCR), with no extra characters.
    name = re.sub(r'\([^)]*\)', '', host)
    handle = re.sub(r'[._]', '', _account(row))
    for noise in (campus | {'the', 'and'}, campus | {'of', 'the', 'and'}):
        initials = ''.join(w[0] for w in re.findall(r'[a-z0-9]+', name) if w not in noise)
        if len(initials) >= 2 and handle in {initials, f'ucr{initials}', f'{initials}ucr'}:
            aliases.append([initials])
    return [alias for alias in aliases if alias]


def _host_venue(row: dict) -> bool:
    """A center/office name alone, without a building or room qualifier."""
    host_words = set(re.findall(r'[a-z0-9]+', str(row.get('host') or '').casefold()))
    return bool(host_words & {'center', 'office', 'library', 'museum'} and any(
        _place_words(row) == _place_words({'location': ' '.join(alias)})
        for alias in _host_aliases(row)))


def _strip_host_prefix(words: list[str], row: dict) -> tuple[list[str], bool]:
    campus = {'ucr', 'uc', 'riverside', 'university', 'california'}
    candidates = [words]
    while candidates[-1] and candidates[-1][0] in campus:
        candidates.append(candidates[-1][1:])
    matches = []
    for candidate in candidates:
        for alias in _host_aliases(row):
            count = 0
            while count < min(len(candidate), len(alias)) and candidate[count] == alias[count]:
                count += 1
            if (count < 2 and count != len(alias)) or not (set(candidate[:count]) - campus):
                continue
            remaining = candidate[count:]
            matches.append(remaining[1:] if remaining[:1] == ['presents'] else remaining)
    return (min(matches, key=len), True) if matches else (words, False)


def _title_form(row: dict, other: dict) -> tuple[set[str], bool]:
    """Normalize titles using aliases corroborated by host/account metadata."""
    words = re.findall(r'[a-z0-9]+', str(row.get('title') or '').casefold())
    if row.get('content_kind') == 'student_deadline' and 'review' in words:
        # Preserve the program identity wherever it occurs in a paraphrase.
        # "First review of applications for X" and "X first review date"
        # describe the same action; interview/final/round qualifiers remain.
        tokens = {'signup' if w in {'application', 'applications', 'registration', 'registrations'} else w
                  for w in words} - _TITLE_NOISE - {'ucr', 'uc', 'riverside', 'university', 'california', 'deadline'}
        tokens -= {'signup', 'date'}
        return tokens, False
    matched = False
    for host_row in (row, other):
        words, found = _strip_host_prefix(words, host_row)
        matched = matched or found
    start = _parse_instant(row.get('starts_at'))
    year = str(start.astimezone(PACIFIC_TZ).year) if start else ''
    tokens = {'celebration' if w == 'gala' else w for w in words} - _TITLE_NOISE - {year}
    if row.get('content_kind') == 'student_deadline':
        tokens = {'signup' if w in {'application', 'applications', 'registration', 'registrations'} else w
                  for w in tokens if w != 'deadline'}
    return tokens, matched


def _equivalent_titles(left: tuple[set[str], bool], right: tuple[set[str], bool]) -> bool:
    a, left_alias = left
    b, right_alias = right
    return bool(a and b and (a == b or (
        left_alias and right_alias and (a <= b or b <= a) and (a & b & _EVENT_NOUNS))))


def _teaser_titles(a: set[str], b: set[str], left: dict, right: dict) -> bool:
    editions = [set(re.findall(r'\b(\d+(?:st|nd|rd|th))\s+annual\b',
                              str(row.get('title') or '').casefold())) for row in (left, right)]
    if bool(editions[0]) != bool(editions[1]):
        a, b = a - editions[0], b - editions[1]
    return a == b


def _title_phrase_in_description(title_row: dict, description_row: dict) -> bool:
    title = ' '.join(re.findall(r'[a-z0-9]+', str(title_row.get('title') or '').casefold()))
    description = ' '.join(re.findall(r'[a-z0-9]+', str(description_row.get('description') or '').casefold()))
    return len(title.split()) >= 2 and bool(re.search(rf'\b{re.escape(title)}\b', description))


def _named_organizer(row: dict, group: list[dict]) -> bool:
    """Prefer the organizer explicitly named by a partner's promotional title."""
    for other in group:
        if not _account(row) or _same_account(row, other):
            continue
        words = re.findall(r'[a-z0-9]+', str(other.get('title') or '').casefold())
        if _strip_host_prefix(words, row)[1]:
            return True
    return False


def same_event(left: dict, right: dict) -> bool:
    """Match corroborated announcements using shared title, owner and place rules."""
    start, other_start = (_parse_instant(r.get('starts_at')) for r in (left, right))
    if start is None or other_start is None or left.get('content_kind') != right.get('content_kind'):
        return False
    # A feed row and a retired story reshare are one post. The two parses may
    # disagree on room or end time.
    if start == other_start and (_source_media(left) & _source_media(right)):
        return True
    place = _same_place(left, right)
    if place == 'conflicting':
        return False
    left_title, right_title = _title_form(left, right), _title_form(right, left)
    a, b = left_title[0], right_title[0]
    common = a & b
    distinctive = common - _GENERIC_WORDS - {'celebration', 'anniversary', 'signup'}
    same_account = _same_account(left, right)
    same_host = _same_host(left, right)
    credited = _credits(left, right) or _credits(right, left)
    rsvp = _rsvp_identity(left.get('rsvp_url'))
    shared_rsvp = bool(rsvp and rsvp == _rsvp_identity(right.get('rsvp_url')))
    equivalent = _equivalent_titles(left_title, right_title)
    if start != other_start:
        if (start.astimezone(PACIFIC_TZ).date() != other_start.astimezone(PACIFIC_TZ).date()
                or _date_only(left) == _date_only(right)):
            return False
        teaser, timed = (left, right) if _date_only(left) else (right, left)
        venue_pending = (same_account and not _place_words(teaser) and bool(_place_words(timed))
                         and re.search(r'\bsave\s+the\s+date\b', str(teaser.get('description') or ''), re.I)
                         and len(distinctive) >= 2)
        # Only exact normalized repeats may use the two-word teaser threshold.
        exact_repeat = same_account and a == b and bool(distinctive)
        # The timed announcement quotes the teaser's whole title: the teaser
        # named this occasion before its time (and possibly venue) was out.
        # Another account also needs the same venue and a distinctive name.
        teaser_words = a if teaser is left else b
        quoted = (_title_phrase_in_description(teaser, timed) and (
            (place == 'same' and len(distinctive) >= 3)
            or (same_account and not _place_words(teaser) and len(distinctive) >= 2
                and teaser_words <= (b if teaser is left else a))))
        return bool(quoted or (
            len(common) >= (2 if exact_repeat else 3) and distinctive
            and _teaser_titles(a, b, left, right)
            and (place == 'same' or venue_pending or exact_repeat)
            and (same_host or credited or shared_rsvp)))
    ends = {_parse_instant(r.get('ends_at')) for r in (left, right)} - {None}
    if len(ends) > 1:
        return False
    if event_key(left) is not None and event_key(left) == event_key(right):
        return True
    short, long = (left, right) if len(a) <= len(b) else (right, left)
    caption_cited = (a <= b or b <= a) and _title_phrase_in_description(short, long)
    repeat = ((equivalent or (same_account and caption_cited))
              and (min(len(a), len(b)) >= 2 or (left_title[1] and right_title[1] and bool(common & _EVENT_NOUNS)))
              and (same_account or (len(distinctive) >= 2 and place == 'same')))
    if left.get('content_kind') == 'student_deadline':
        # Two clubs relaying one cutoff with the same registration form.
        return bool(equivalent and distinctive and (same_account or shared_rsvp or (
            credited and len(distinctive - {'first', 'review', 'date', 'program', 'applications'}) >= 2)))
    qualified_variant = (a <= b or b <= a) and (a ^ b) <= _TITLE_QUALIFIERS | _PRESENTATION_WORDS
    return bool(repeat or (shared_rsvp and len(common) >= 2)
                or (len(distinctive) >= 2 and (credited or ((place == 'same' or same_host) and qualified_variant))))


def _reconciliation_rows() -> list[dict]:
    from db import get_event_rows
    return [row for row in get_event_rows() if imported_row_kind(row) != 'other']


def plan(rows: list[dict], tombstones: list[dict] = (), *, now: datetime | None = None
         ) -> tuple[list[dict], set[str], dict[str, str]]:
    """Return canonical updates, removed IDs and duplicate-to-canonical mappings.

    Removed IDs absent from replacements are exclusively tombstone suppression.
    Retired campus rows may only be removed in favor of an Instagram import.
    """
    kinds = {row['id']: imported_row_kind(row) for row in rows}
    rows = [row for row in rows if kinds[row['id']] != 'other']
    groups: list[list[dict]] = []
    blocked = {r["id"] for r in tombstones}
    by_id = {r["id"]: r for r in rows}
    candidates = [*rows, *(r for r in tombstones if r['id'] not in by_id)]
    # A teaser for two different timed sessions does not identify either one.
    ambiguous = {row['id'] for row in candidates if _date_only(row) and len({
        _parse_instant(other.get('starts_at')) for other in candidates
        if not _date_only(other) and same_event(row, other)
    }) > 1}
    # An abbreviated conference title or an organizer-only venue must not
    # bridge two separately specified events. Include tombstones in this check.
    ambiguous_details = set()
    for row in candidates:
        title, alias = _title_form(row, row)
        vague_title = alias and bool(title) and title <= _EVENT_NOUNS
        vague_venue = _host_venue(row)
        if not (vague_title or vague_venue):
            continue
        peers = [other for other in candidates if other['id'] != row['id'] and same_event(row, other)]
        for i, left in enumerate(peers):
            for right in peers[i + 1:]:
                a, b = _title_form(left, right)[0], _title_form(right, left)[0]
                if ((vague_title and not (a <= b or b <= a))
                        or (vague_venue and _same_place(left, right) == 'conflicting')):
                    ambiguous_details.add(row['id'])
    def matches_pair(left, right):
        if {left['id'], right['id']} & ambiguous_details:
            return False
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
    updates, tombstoned, replacements = [], set(), {}
    for group in groups:
        live = [r for r in group if r['id'] in by_id]
        if any(r['id'] in blocked for r in group):
            tombstoned.update(r['id'] for r in live if not r.get('is_locked')
                              and kinds[r['id']] == 'instagram')
            continue
        if len(live) < 2:
            continue
        if now and all((_parse_instant(r.get('ends_at') or r.get('starts_at')) or now) < now for r in live):
            continue
        winner = max(live, key=lambda r: (bool(r.get('is_locked')), not _date_only(r),
                     kinds[r['id']] == 'instagram',
                     _named_organizer(r, live), _row_score(r)))
        duplicates = {r['id'] for r in live if r['id'] != winner['id'] and not r.get('is_locked')
                      and (kinds[r['id']] == 'instagram' or kinds[winner['id']] == 'instagram')}
        if not duplicates:
            continue
        replacements.update((event_id, winner['id']) for event_id in duplicates)
        if winner.get('is_locked'):
            continue
        merged = merge_duplicates(winner, live)
        if merged != winner:
            updates.append(merged)
    return updates, tombstoned | replacements.keys(), replacements


def merge_duplicates(winner: dict, live: list[dict]) -> dict:
    """The canonical row with the details its corroborated duplicates add."""
    merged = dict(winner)
    merged['has_free_food'] = any(r.get('has_free_food') for r in live)
    # A partner's registration can target a restricted audience (e.g.
    # graduate wristbands). Do not turn it into the organizer's signup.
    signup_rows = [r for r in live if r['id'] == winner['id'] or
                   _same_host(winner, r)]
    if any(r.get('rsvp_required') for r in signup_rows):
        merged['rsvp_required'] = True
    hosts = _merged_hosts(winner, live)
    if len(hosts) > 1 or winner.get('hosts'):
        merged['hosts'] = hosts
    for key in ('ends_at', 'rsvp_url', 'image_url', 'location'):
        if not merged.get(key) or (key == 'location' and _host_venue(winner)):
            options = {r[key] for r in (signup_rows if key == 'rsvp_url' else live) if r.get(key)
                       and not (key == 'location' and _host_venue(r))
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
    return merged


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


def _inherit_notifications(rows: list[dict], updates: list[dict], canonical_ids: dict[str, str]) -> None:
    """Transfer sent alerts only along the planner's explicit duplicate mappings."""
    from db import client
    from discord_notify import free_food_notification_key
    by_row_id = {r['id']: r for r in rows}
    survivors = {r['id']: r for r in rows if r['id'] not in canonical_ids}
    survivors.update({r['id']: r for r in updates})
    replacements: dict[str, list[dict]] = {}
    for event_id, canonical_id in canonical_ids.items():
        # Missing mappings are tombstones, never an invitation to match again.
        if canonical_id not in survivors:
            raise ValueError(f'Canonical notification replacement is missing: {canonical_id}')
        replacements.setdefault(canonical_id, []).append(by_row_id[event_id])
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
    from db import client, get_deleted_event_ids
    from discord_notify import notify_free_food_events
    rows = _reconciliation_rows()
    updates, removed, replacements = plan(rows, _tombstoned_candidates(get_deleted_event_ids()), now=datetime.now(timezone.utc))
    original = {row['id']: row for row in rows}
    for row in updates:
        before = original[row['id']]
        changes = {key: value for key, value in row.items() if value != before.get(key)}
        query = client().table('events').update(changes).eq('id', row['id']).eq('is_locked', False)
        if before.get('updated_at'):
            query = query.eq('updated_at', before['updated_at'])
        if len(query.execute().data or []) != 1:
            raise RuntimeError(f"Canonical event changed during reconciliation: {row['id']}")
    _inherit_notifications(rows, updates, replacements)
    removals = []
    for event_id in sorted(removed):
        removals.append({
            'id': event_id,
            'replacement_id': replacements.get(event_id),
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
