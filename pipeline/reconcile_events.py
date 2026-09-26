"""Reconcile corroborated duplicates across the independently published sources.

Run after imports (even partially failed ones). Canonical updates are saved
before unlocked duplicates are removed. Dry-run planning is pure; locked and
admin-deleted identities constrain the whole corroborated group.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import NamedTuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from event_identity import _parse_instant, _row_score, event_key, imported_row_kind
from event_dates import PACIFIC_TZ
from instagram_rows import POST_EVENT_ID

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
# Current rows end in _p<media_id>, plus a session key when the post lists
# several; retired story reshares were keyed on the original post as
# ig_post_<media_id>_<minute>.
_MEDIA_ID = re.compile(r"ig_post_(\d+)_\d{8}T\d{4}Z|ig_.+_p(\d+)(?:-[0-9A-Za-z]+)*")
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


def _sibling_sessions(left: dict, right: dict) -> bool:
    """Two sessions one post lists separately, as its assessment split them."""
    ids = [str(row.get("id") or "") for row in (left, right)]
    matches = [POST_EVENT_ID.fullmatch(event_id) for event_id in ids]
    return (ids[0] != ids[1] and all(matches)
            and matches[0].group(1, 2) == matches[1].group(1, 2))


def _session_row(row: dict) -> bool:
    """One session of a post that lists several."""
    match = POST_EVENT_ID.fullmatch(str(row.get("id") or ""))
    return bool(match and match.group(3))


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
    """Venue words, spelled one way. Empty when the location names no venue."""
    location = str(row.get('location') or '').casefold()
    for pattern, replacement in _VENUE_SPELLINGS:
        location = re.sub(pattern, replacement, location)
    words = set(re.findall(r'[a-z]+|[0-9]+', location))
    if words & _VIRTUAL_WORDS:
        words = (words - _VIRTUAL_WORDS - {'via', 'link', 'in', 'bio'}) | {'virtual'}
    return words - _PLACE_NOISE


# City and state suffixes: "Culver Center of the Arts, Riverside, CA" and
# "..., Downtown Riverside" name the same venue. Placeholders (TBA, Room TBD,
# Invite Only) and a bare region (SoCal) name no venue at all.
_PLACE_NOISE = frozenset('the and at of ucr uc riverside university california campus ca downtown usa '
                         'tba tbd announced determined room rm by near invite only socal'.split())
_VIRTUAL_WORDS = frozenset('zoom online virtual remote webinar discord'.split())
# One campus venue written several ways: "SSC 114", "SSC114", "Student
# Success Center 114"; "Pentland Bear Cave" and "Pentland Bearcave".
_VENUE_SPELLINGS = (
    (r'https?://\S+', lambda m: ' zoom ' if 'zoom.' in m.group(0) else ' '),
    (r'\bstudent success center\b', 'ssc'),
    (r'\bwinston chung(?: hall)?\b', 'wch'),
    (r'\bhighlander union(?: building)?\b', 'hub'),
    (r'\bbell\s*tower\b', 'belltower'),
    (r'\bbear\s*cave\b', 'bearcave'),
    (r'\ba-i\b', 'ai'),
    (r'\b([a-z]+)(\d+)\b', r'\1 \2'),
)
# Words shared by unrelated venues, and bare room numbers without a building.
_VENUE_FILLER = frozenset('hall building center lawn lobby park plaza patio courtyard field fields '
                          'street st ave avenue drive dr way north south east west upper lower mpr'.split())


def _shared_venue(left: dict, right: dict) -> bool:
    """Whether two locations share a naming word (Lake Alice Bar & Grill and
    Lake Alice Trading Co.) without naming different rooms (Costo Hall 111
    and Costo Hall 112)."""
    a, b = _place_words(left), _place_words(right)
    rooms = [{word for word in words if word.isdigit()} for words in (a, b)]
    if rooms[0] and rooms[1] and not rooms[0] & rooms[1]:
        return False
    return any(not word.isdigit() and word not in _VENUE_FILLER for word in a & b)


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


def _specific_slot(row: dict) -> bool:
    """A start and end that pin down an occasion: a time of day, or several
    whole days. A single bare date (deadlines, undated teasers) does not."""
    start, end = _parse_instant(row.get('starts_at')), _parse_instant(row.get('ends_at'))
    if start is None or _date_only(row) or row.get('content_kind') == 'student_deadline':
        return False
    if start.astimezone(PACIFIC_TZ).time().isoformat() != '00:00:00':
        return True
    return bool(end and (end - start).total_seconds() > 86400)


def _same_slot(left: dict, right: dict) -> bool:
    return (_specific_slot(left) and _specific_slot(right)
            and all(_parse_instant(left.get(key)) == _parse_instant(right.get(key))
                    for key in ('starts_at', 'ends_at')))


def _slot_title_words(row: dict) -> set[str]:
    words = re.findall(r'[a-z0-9]+', str(row.get('title') or '').casefold())
    return {word for word in words if len(word) > 1} - _GENERIC_WORDS - _TITLE_NOISE


def _own_name_words(row: dict) -> set[str]:
    return {word for alias in _host_aliases(row) for word in alias} | {_account(row)}


def _same_slot_event(left: dict, right: dict, place: str) -> bool:
    """One occasion posted twice, identified by its exact start and end.

    An account does not hold two different events with the same start and end;
    across 725 production rows every such pair was a repeat (a schedule post
    and the event's own post, a renamed or corrected flyer). The title may
    change completely ("Boba Social" and "Designing Dreams Social"). A room
    that the account writes differently still counts; two disjoint venues do
    not. Titles naming different occurrences (another year or session) never
    match. Another account at the same slot must name the occasion in the same
    place: one title contains the other's distinctive words. "KDSAP at
    Involvement Fair" is KDSAP's table at the fair, not a repost of it, so a
    title that only adds its own club's name stays.
    """
    if not _same_slot(left, right) or _contradicting_titles(left, right):
        return False
    if _same_account(left, right):
        return place != 'conflicting' or _shared_venue(left, right)
    if place != 'same':
        return False
    short, long = sorted((left, right), key=lambda row: len(_slot_title_words(row)))
    words, other = _slot_title_words(short), _slot_title_words(long)
    return bool(words and words <= other and not ((other - words) & _own_name_words(long)))


_SEQUENCE = re.compile(r'\b(?:session|part|day|round|week|vol|no)\.?\s*#?\s*(\d+)\b|#\s*(\d+)')
_EDITION = re.compile(r'\b(\d+)(?:st|nd|rd|th)\s+annual\b')


def _contradicting_titles(left: dict, right: dict) -> bool:
    """Titles that name different occurrences: another year ("Silent Disglo
    2027"), session ("Session 2", "GM #4") or edition ("13th Annual")."""
    titles = [str(row.get('title') or '').casefold() for row in (left, right)]
    start = _parse_instant(left.get('starts_at'))
    year = str(start.astimezone(PACIFIC_TZ).year) if start else ''
    if any(y != year for title in titles for y in re.findall(r'\b20\d\d\b', title)):
        return True
    sequences = [{a or b for a, b in _SEQUENCE.findall(title)} for title in titles]
    editions = [set(_EDITION.findall(title)) for title in titles]
    return sequences[0] != sequences[1] or bool(editions[0] and editions[1] and editions[0] != editions[1])


def _corrected_deadline(left: dict, right: dict) -> bool:
    """A reposted deadline for one application whose date was corrected.

    One application closes once. The same account repeating the same deadline
    title for the same form (or the same caption with only its date changed)
    within a month is a correction, not a second cutoff.
    """
    if left.get('content_kind') != 'student_deadline' or not _same_account(left, right):
        return False
    if _source_media(left) & _source_media(right) or not _source_media(left) or not _source_media(right):
        return False
    starts = [_parse_instant(row.get('starts_at')) for row in (left, right)]
    if abs((starts[0] - starts[1]).days) > 31:
        return False
    titles = [set(re.findall(r'[a-z0-9]+', str(row.get('title') or '').casefold())) for row in (left, right)]
    rsvp = _rsvp_identity(left.get('rsvp_url'))
    shared_rsvp = bool(rsvp and rsvp == _rsvp_identity(right.get('rsvp_url')))
    return bool(titles[0]) and titles[0] == titles[1] and (shared_rsvp or _same_caption_template(left, right))


def _same_caption_template(left: dict, right: dict) -> bool:
    captions = [re.sub(r'\d+(?:st|nd|rd|th)?|\b(?:' + _DATE_WORDS + r')\w*', '#',
                       str(row.get('description') or '').casefold()) for row in (left, right)]
    return len(captions[0]) >= 80 and captions[0] == captions[1]


_DATE_WORDS = 'jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|mon|tue|wed|thu|fri|sat|sun'


def _incomplete_session(row: dict) -> bool:
    """A multi-event post's entry that omits a time or a specific venue."""
    return (_session_row(row) and row.get('content_kind') == 'student_event'
            and (_date_only(row) or not _place_words(row)))


def _summary_detail_match(summary: dict, detailed: dict) -> bool:
    """Resolve an incomplete schedule entry to a named, timed announcement.

    The session suffix records that assessment split this post into multiple
    occurrences. Such entries commonly omit time/place and their publisher
    need not be the organizer. Omitted fields can be supplied by a detailed
    announcement; explicit conflicting fields and different activities cannot.
    Group planning and republication must also check competing announcements.
    """
    if (not _incomplete_session(summary) or detailed.get('content_kind') != 'student_event'
            or not _specific_slot(detailed) or not _place_words(detailed)
            or _sibling_sessions(summary, detailed) or _contradicting_titles(summary, detailed)
            or _same_place(summary, detailed) == 'conflicting'):
        return False
    start, other_start = (_parse_instant(row.get('starts_at')) for row in (summary, detailed))
    if not start or start.astimezone(PACIFIC_TZ).date() != other_start.astimezone(PACIFIC_TZ).date():
        return False
    if not _date_only(summary):
        ends = {_parse_instant(row.get('ends_at')) for row in (summary, detailed)} - {None}
        if start != other_start or len(ends) > 1:
            return False
    a, b = _title_form(summary, detailed)[0], _title_form(detailed, summary)[0]
    distinctive = a - _GENERIC_WORDS - {'celebration', 'anniversary', 'signup'}
    return (a == b and len(a) >= 2
            and len(distinctive) >= (1 if _same_account(summary, detailed) else 2))


def same_event(left: dict, right: dict) -> bool:
    """Match corroborated announcements using shared title, owner and place rules."""
    start, other_start = (_parse_instant(r.get('starts_at')) for r in (left, right))
    if start is None or other_start is None or left.get('content_kind') != right.get('content_kind'):
        return False
    # Sessions of one post share its caption, link and flyer, and can share a
    # start. They are still different events.
    if _sibling_sessions(left, right):
        return False
    # A feed row and a retired story reshare are one post. The two parses may
    # disagree on room or end time.
    if start == other_start and (_source_media(left) & _source_media(right)):
        return True
    place = _same_place(left, right)
    if _same_slot_event(left, right, place) or (start != other_start and _corrected_deadline(left, right)):
        return True
    if place == 'conflicting':
        return False
    if _summary_detail_match(left, right) or _summary_detail_match(right, left):
        return True
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


def _summary_group_conflict(rows: list[dict]) -> bool:
    """A vague schedule entry cannot join incompatible detailed announcements."""
    if not any(_incomplete_session(row) for row in rows):
        return False
    detailed = [row for row in rows if _specific_slot(row) and _place_words(row)]
    return any(not same_event(left, right)
               for i, left in enumerate(detailed) for right in detailed[i + 1:])


def _ambiguous_summaries(rows: list[dict]) -> set[str]:
    """Reject competing events, including different venues at the same time."""
    detailed = [row for row in rows if _specific_slot(row) and _place_words(row)]
    return {row['id'] for row in rows if _incomplete_session(row)
            and _summary_group_conflict([row, *(other for other in detailed if same_event(row, other))])}


class Reviews(NamedTuple):
    """Admin decisions from the duplicate review queue, which override the rules.

    merged maps each listing an admin merged away to the listing kept; distinct
    holds the pairs an admin judged to be different events.
    """
    merged: dict[str, str] = {}
    distinct: frozenset[frozenset[str]] = frozenset()

    @classmethod
    def from_queue(cls, queue: list[dict]) -> Reviews:
        merged, distinct = {}, set()
        for review in queue:
            pair = {review['event_id'], review['other_event_id']}
            if review['status'] == 'duplicate':
                merged[(pair - {review['kept_event_id']}).pop()] = review['kept_event_id']
            elif review['status'] == 'different':
                distinct.add(frozenset(pair))
        return cls(merged, frozenset(distinct))

    def kept(self, event_id: str) -> str | None:
        """The listing an admin merged event_id into, following later merges."""
        seen = {event_id}
        while (following := self.merged.get(event_id)) and following not in seen:
            seen.add(event_id := following)
        return event_id if len(seen) > 1 else None

    def judged_distinct(self, rows: list[dict]) -> bool:
        ids = [row['id'] for row in rows]
        return any(frozenset((a, b)) in self.distinct for i, a in enumerate(ids) for b in ids[i + 1:])


def load_reviews() -> tuple[Reviews, list[dict]]:
    """Admin decisions, and the queue they were read from."""
    from db import get_duplicate_reviews
    queue = get_duplicate_reviews()
    return Reviews.from_queue(queue), queue


# Words every application or signup deadline shares; they name no program.
_DEADLINE_BOILERPLATE = frozenset('application applications deadline registration recruitment program due'.split())


def review_candidates(rows: list[dict], *, now: datetime | None = None,
                      reviews: Reviews = Reviews()) -> list[tuple[dict, dict]]:
    """Upcoming pairs that look alike but no rule merged, for human review.

    The rules merge only corroborated repeats; a new kind of repost (another
    wording, venue or account) first appears here instead of silently on the
    site. Pairs overlap on one day and either come from one account at one
    start, or share two distinctive title words. A pair an admin already
    judged different is not asked about again.
    """
    def span(row):
        start = _parse_instant(row.get('starts_at'))
        return start, _parse_instant(row.get('ends_at')) or start

    live = sorted((row for row in rows if span(row)[0] and not (now and span(row)[1] < now)),
                  key=lambda row: (span(row)[0], row['id']))
    pairs = []
    for i, left in enumerate(live):
        start, end = span(left)
        for right in live[i + 1:]:
            other_start = span(right)[0]
            if other_start.astimezone(PACIFIC_TZ).date() != start.astimezone(PACIFIC_TZ).date():
                break
            if (other_start > end or left.get('content_kind') != right.get('content_kind')
                    or _sibling_sessions(left, right) or reviews.judged_distinct([left, right])
                    or same_event(left, right)):
                continue
            shared = (_slot_title_words(left) & _slot_title_words(right)) - _DEADLINE_BOILERPLATE
            if (_same_account(left, right) and start == other_start and _specific_slot(left)
                    and _specific_slot(right)) or len(shared) >= 2:
                pairs.append((left, right))
    return pairs


def _reconciliation_rows() -> list[dict]:
    from db import get_event_rows
    return [row for row in get_event_rows() if imported_row_kind(row) != 'other']


class _CandidateIndex:
    """Necessary matching conditions only; same_event remains the policy.

    Cross-date matches are exclusively corrected deadlines by the same owner.
    Include historical rows and tombstones so old identities still constrain
    current publications. Cache dates once per invocation.
    """
    def __init__(self, rows: list[dict]):
        self.days = {}
        self.by_day = {}
        self.deadlines = {}
        for row in rows:
            start = _parse_instant(row.get('starts_at'))
            day = start.astimezone(PACIFIC_TZ).date() if start else None
            self.days[row['id']] = day
            if day is None:
                continue
            self.by_day.setdefault((row.get('content_kind'), day), []).append(row)
            if row.get('content_kind') == 'student_deadline' and _account(row):
                self.deadlines.setdefault((_account(row), day), []).append(row)

    def peers(self, row: dict) -> list[dict]:
        day = self.days[row['id']]
        if day is None:
            return []
        peers = list(self.by_day.get((row.get('content_kind'), day), ()))
        if row.get('content_kind') == 'student_deadline' and _account(row):
            # timedelta.days in the matcher and DST can cross a date boundary.
            for delta in range(-32, 33):
                if delta:
                    peers.extend(self.deadlines.get((_account(row), day + timedelta(days=delta)), ()))
        return peers


def plan(rows: list[dict], tombstones: list[dict] = (), *, now: datetime | None = None,
         reviews: Reviews = Reviews()) -> tuple[list[dict], set[str], dict[str, str]]:
    """Return canonical updates, removed IDs and duplicate-to-canonical mappings.

    Removed IDs absent from replacements are exclusively tombstone suppression.
    Retired campus rows may only be removed in favor of an Instagram import.
    Admin reviews override the rules: a listing merged away that its source
    recreated joins the listing kept, and a pair judged different never merges.
    """
    kinds = {row['id']: imported_row_kind(row) for row in rows}
    rows = [row for row in rows if kinds[row['id']] != 'other']
    groups: list[list[dict]] = []
    blocked = {r["id"] for r in tombstones}
    by_id = {r["id"]: r for r in rows}
    forced = {event_id: kept for event_id in by_id if (kept := reviews.kept(event_id)) in by_id}
    # Decisions that loop back on themselves name no listing to keep.
    forced = {event_id: kept for event_id, kept in forced.items() if kept not in forced}
    candidates = [*(r for r in rows if r['id'] not in forced),
                  *(r for r in tombstones if r['id'] not in by_id)]
    index = _CandidateIndex(candidates)
    # A teaser for two different timed sessions does not identify either one.
    ambiguous = {row['id'] for row in candidates if _date_only(row) and len({
        _parse_instant(other.get('starts_at')) for other in index.peers(row)
        if not _date_only(other) and same_event(row, other)
    }) > 1}
    # An abbreviated conference title or an organizer-only venue must not
    # bridge two separately specified events. Include tombstones in this check.
    ambiguous_details = {row['id'] for row in candidates if _incomplete_session(row)
                         and _summary_group_conflict([row, *(other for other in index.peers(row)
                             if _specific_slot(other) and _place_words(other) and same_event(row, other))])}
    for row in candidates:
        title, alias = _title_form(row, row)
        vague_title = alias and bool(title) and title <= _EVENT_NOUNS
        vague_venue = _host_venue(row)
        if not (vague_title or vague_venue):
            continue
        peers = [other for other in index.peers(row) if other['id'] != row['id'] and same_event(row, other)]
        for i, left in enumerate(peers):
            for right in peers[i + 1:]:
                a, b = _title_form(left, right)[0], _title_form(right, left)[0]
                if ((vague_title and not (a <= b or b <= a))
                        or (vague_venue and _same_place(left, right) == 'conflicting')):
                    ambiguous_details.add(row['id'])
    def matches_pair(left, right):
        if {left['id'], right['id']} & ambiguous_details or reviews.judged_distinct([left, right]):
            return False
        if ({left['id'], right['id']} & ambiguous
                and _parse_instant(left.get('starts_at')) != _parse_instant(right.get('starts_at'))):
            return False
        return same_event(left, right)
    group_for = {}
    group_order = {}
    for position, row in enumerate(sorted(candidates, key=lambda r:r['id'])):
        plausible = {id(group_for[other['id']]): group_for[other['id']]
                     for other in index.peers(row) if other['id'] in group_for}
        matches = [g for g in sorted(plausible.values(), key=lambda g: group_order[id(g)])
                   if any(matches_pair(row, other) for other in g)]
        # Nor may a third listing bridge a pair judged different.
        joined = [row, *(other for group in matches for other in group)]
        if _summary_group_conflict(joined) or reviews.judged_distinct(joined):
            matches = []
        # Two related date-only teasers must not bridge incompatible sessions.
        # A corrected deadline replaces its old date rather than bridging it.
        timed = [r for r in [row, *(r for group in matches for r in group)] if not _date_only(r)]
        if len({_parse_instant(r.get('starts_at')) for r in timed}) > 1 and not all(
                _corrected_deadline(a, b) for i, a in enumerate(timed) for b in timed[i + 1:]
                if a.get('starts_at') != b.get('starts_at')):
            matches = []
        if matches:
            first = matches[0]
            first.append(row)
            for group in matches[1:]:
                first.extend(group)
                groups.remove(group)
            for member in first:
                group_for[member['id']] = first
        else:
            group = [row]
            group_order[id(group)] = position
            groups.append(group)
            group_for[row['id']] = group
    for event_id, kept in forced.items():
        next(group for group in groups if any(r['id'] == kept for r in group)).append(by_id[event_id])
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
        # A post about one event names and pictures it better than a line in a
        # schedule post, whose caption is longer but covers every session.
        # Rows on different days are a corrected deadline: the newest post's
        # date is the current one.
        revised = len({_parse_instant(r['starts_at']).astimezone(PACIFIC_TZ).date() for r in live}) > 1
        winner = max(live, key=lambda r: (r['id'] not in forced, bool(r.get('is_locked')), not _date_only(r),
                     kinds[r['id']] == 'instagram',
                     _named_organizer(r, live), not _session_row(r),
                     max(map(int, _source_media(r)), default=0) if revised else 0, _row_score(r)))
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
    # A corrected deadline's superseded date must not stretch its end.
    start = _parse_instant(winner.get('starts_at'))
    same_day = [r for r in live if start and (_parse_instant(r.get('starts_at')) or start)
                .astimezone(PACIFIC_TZ).date() == start.astimezone(PACIFIC_TZ).date()]
    for key in ('ends_at', 'rsvp_url', 'image_url', 'location'):
        # A placeholder (TBA, Room TBD) or bare campus location names no venue.
        vague = key == 'location' and (_host_venue(winner) or not _place_words(winner))
        if not merged.get(key) or vague:
            pool = signup_rows if key == 'rsvp_url' else same_day if key == 'ends_at' else live
            options = {r[key] for r in pool if r.get(key)
                       and not (key == 'location' and (_host_venue(r) or not _place_words(r)))
                       and not (key == 'ends_at' and _date_only(r) and not _date_only(winner))}
            if len(options) == 1:
                merged[key] = options.pop()
    # Date-only weekend announcements often omit the end on the campus
    # listing. The corrected flyers supply the complete final day.
    if start and start.astimezone(PACIFIC_TZ).time().isoformat() == '00:00:00':
        ends = [_parse_instant(r.get('ends_at')) for r in same_day]
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
    from db import client, get_deleted_event_ids, queue_duplicate_reviews
    from discord_notify import notify_free_food_events
    rows = _reconciliation_rows()
    reviews, queue = load_reviews()
    updates, removed, replacements = plan(rows, _tombstoned_candidates(get_deleted_event_ids()),
                                          now=datetime.now(timezone.utc), reviews=reviews)
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
    canonical = {r['id']:r for r in rows if r['id'] not in removed}
    canonical.update({r['id']:r for r in updates})
    suspects = review_candidates(list(canonical.values()), now=datetime.now(timezone.utc), reviews=reviews)
    for left, right in suspects:
        log.warning('Possible duplicate for review: %s %r (@%s) and %s %r (@%s)',
                    left['id'], left.get('title'), left.get('host_handle'),
                    right['id'], right.get('title'), right.get('host_handle'))
    queue_duplicate_reviews([(left['id'], right['id']) for left, right in suspects], queue)
    log.info('%d possible duplicates queued for admin review', len(suspects))
    if notify:
        sent = notify_free_food_events(canonical.values())
        log.info('Sent %d free food Discord notifications', sent)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
