"""Reconcile corroborated duplicates across the independently published sources.

Run after imports (even partially failed ones). Canonical updates are saved
before unlocked duplicates are removed. Dry-run planning is pure; locked and
admin-deleted identities constrain the whole corroborated group.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from typing import NamedTuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from event_identity import _parse_instant, _row_score, event_key, imported_row_kind
from event_dates import PACIFIC_TZ
from instagram_rows import POST_EVENT_ID

log = logging.getLogger("pipeline.reconcile_events")
_GENERIC_WORDS = frozenset("first second third general body meeting club weekly monthly annual fall winter spring summer welcome back workshop session orientation open house social event ucr uc riverside university california of at the and for to a an".split())
_TITLE_NOISE = frozenset("the of at and for to a an annual save date".split())
_SEASONS = frozenset("fall winter spring summer quarter".split())
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
# Success Center 114"; "Pentland Bear Cave" and "Pentland Bearcave";
# "Student Recreation Center", "Rec Center" and "SRC"; "SSB" and "Student
# Services Bldg."; "SBB RM 202" and "School of Business Building, Room 202".
_VENUE_SPELLINGS = (
    (r'https?://\S+', lambda m: ' zoom ' if 'zoom.' in m.group(0) else ' '),
    (r'\bstudent success center\b', 'ssc'),
    (r'\bstudent services (?:building|bldg)\b', 'ssb'),
    (r'\bschool of business(?: building)?\b', 'sbb'),
    (r'\b(?:student\s+)?rec(?:reation)?\s+center\b', 'src'),
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
# How a post happens to write a building, not which one: "APSP (244 Costo
# Hall)" and "APSP Center 244 Costo". A lawn, plaza or lobby is a place of
# its own (HUB Plaza is not HUB 302), as is a wing (HUB 302 North and South).
_BUILDING_KINDS = frozenset('hall building bldg center'.split())


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
    named = [words - _BUILDING_KINDS for words in (a, b)]
    if ((named[0] <= named[1] or named[1] <= named[0])
            and any(not word.isdigit() for word in named[0] & named[1])):
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
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    query = [(k, v) for k, v in parse_qsl(parsed.query) if k != "fbclid" and not k.startswith("utm_")]
    # A bare site (ucr.scholarshipuniverse.com/) names no form. A root address
    # whose query carries one does: gateway.campuslogic.com/?...ctx=/student/
    # scholarship/607387.
    if parsed.path.rstrip("/") == "" and not query:
        return None
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


def _title_text(value: str) -> str:
    return ''.join(char for char in unicodedata.normalize('NFKD', value.casefold())
                   if not unicodedata.combining(char))


def _title_form(row: dict, other: dict) -> tuple[set[str], bool]:
    """Normalize titles using aliases corroborated by host/account metadata."""
    words = re.findall(r'[a-z0-9]+', _title_text(str(row.get('title') or '')))
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
    title = ' '.join(re.findall(r'[a-z0-9]+', _title_text(str(title_row.get('title') or ''))))
    start = _parse_instant(title_row.get('starts_at'))
    if start:
        title = ' '.join(re.sub(rf'\b{start.astimezone(PACIFIC_TZ).year}\b', '', title).split())
    description = ' '.join(re.findall(r'[a-z0-9]+', _title_text(str(description_row.get('description') or ''))))
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
    words = re.findall(r'[a-z0-9]+', _title_text(str(row.get('title') or '')))
    return {word for word in words if len(word) > 1} - _GENERIC_WORDS - _TITLE_NOISE


def _own_name_words(row: dict) -> set[str]:
    return {word for alias in _host_aliases(row) for word in alias} | {_account(row)}


def _held_at(row: dict, occasion: set[str]) -> bool:
    """Whether a title places an activity of its own at the named occasion.

    "Depop at UCR Pop-up at Once Upon a Faire" is a stall at the fair, not the
    fair. "CHASS Academic Advising at LGBT Resource Center" names a venue: the
    occasion's words come before "at", so it is still that advising hour.
    """
    title = _title_text(str(row.get('title') or ''))
    return any(occasion <= _slot_title_words({'title': title[match.end():]})
               and bool(_slot_title_words({'title': title[:match.start()]}))
               for match in re.finditer(r'\s(?:at|@)\s', title))


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
    title that only adds its own club's name stays, as does one that places
    an activity of its own at the occasion.
    """
    if not _same_slot(left, right) or _contradicting_titles(left, right):
        return False
    if _same_account(left, right):
        return place != 'conflicting' or _shared_venue(left, right)
    if place != 'same':
        return False
    short, long = sorted((left, right), key=lambda row: len(_slot_title_words(row)))
    words, other = _slot_title_words(short), _slot_title_words(long)
    return bool(words and words <= other and not ((other - words) & _own_name_words(long))
                and not _held_at(long, words))


def _unnumbered_repeat(left: dict, right: dict, place: str) -> bool:
    """One account's occasion at one start and venue, numbered by one post only.

    Elite Healthcare Hospice's October calendar lists "GM#1 - Intro to Hospice"
    and "Night at the Rec!" ("4PM-PM": OCR lost the end); its earlier timeline
    lists "First Member Meeting" and "Night at the SRC" at the same starts and
    venues. HBS's schedule says "Professional Night"; its own post says
    "Recruitment Day 3: Professional Night". An account holds one occasion in
    one venue at one start, so a session number only one title carries and an
    end only one post prints do not separate them. Different numbers, years
    or editions, different rooms and different ends still do.
    """
    if (place != 'same' or not _same_account(left, right) or not _specific_slot(left)
            or not _specific_slot(right) or not _shared_venue(left, right)
            or _parse_instant(left.get('starts_at')) != _parse_instant(right.get('starts_at'))
            or _contradicting_titles(left, right, numbered_once=True)):
        return False
    return len({_parse_instant(row.get('ends_at')) for row in (left, right)} - {None}) <= 1


_LATIN = frozenset('latin latinx latine latino latina latinos latinas'.split())


def _shared_occasion_name(left: dict, right: dict, place: str) -> bool:
    """One named occasion relayed by different accounts at one slot and venue.

    Chicano Student Programs' "Latinx Heritage Soccer Night", Athletics'
    "MSOC: Highlanders Game (Latin Heritage Night)" and the team's "Latin
    Heritage Night: UCR Men's Soccer vs. UC San Diego" all start at 7 PM at the
    UCR Soccer Stadium. Neither title contains the other, so _same_slot_event
    cannot match them; three shared distinctive words can. A club's own part
    in a larger occasion ("UCRaas Performance ... at SAF Night Market") is a
    separate listing, as is a pair whose ends disagree.
    """
    if (place != 'same' or _same_account(left, right) or left.get('content_kind') != 'student_event'
            or not _specific_slot(left) or not _specific_slot(right) or not _shared_venue(left, right)
            or _parse_instant(left.get('starts_at')) != _parse_instant(right.get('starts_at'))
            or len({_parse_instant(row.get('ends_at')) for row in (left, right)} - {None}) > 1
            or any(re.search(r'\S\s+at\s+\S', str(row.get('title') or ''), re.I) for row in (left, right))):
        return False
    words = [{'latin' if word in _LATIN else word for word in _slot_title_words(row)} for row in (left, right)]
    common = words[0] & words[1] - _own_name_words(left) - _own_name_words(right)
    return len(common) >= 3


def _schedule_superseded(left: dict, right: dict) -> bool:
    """A schedule post's entry and the account's later post for that occasion.

    A quarter schedule is published weeks ahead; the club's own post for one
    entry, at the same start, is the current word on it even when its title
    ("First General Meeting" and "Trivia Night"), room (HUB 269 and HUB 260,
    one building) or end differs. The end may differ only while the schedule
    names no venue to corroborate the occasion; a post that omits its end
    does not contradict one. Two dedicated posts in
    different rooms, or any two different buildings, stay apart.
    """
    if not _same_account(left, right) or left.get('starts_at') is None:
        return False
    entry, post = (left, right) if _session_row(left) else (right, left)
    if (not _session_row(entry) or _session_row(post) or not _specific_slot(entry) or not _specific_slot(post)
            or _parse_instant(entry['starts_at']) != _parse_instant(post.get('starts_at'))
            or _contradicting_titles(entry, post)):
        return False
    older, newer = (max(map(int, _source_media(row)), default=0) for row in (entry, post))
    if not older or newer <= older:
        return False
    if not _place_words(entry):
        return True
    ends = {_parse_instant(row.get('ends_at')) for row in (entry, post)} - {None}
    return len(ends) <= 1 and (_same_place(entry, post) != 'conflicting' or any(
        not word.isdigit() and word not in _VENUE_FILLER
        for word in _place_words(entry) & _place_words(post)))


def _same_multiday_span(left: dict, right: dict, place: str) -> bool:
    """One conference or weekend relayed by several accounts.

    Identical whole-day spans of several days, where one title names the
    other's occasion ("Family Weekend" in "Highlander Family Weekend 2026",
    "USM's 13th Annual Conference" with its theme appended). A title that
    only adds the poster's own name stays a separate listing.
    """
    start, end = _parse_instant(left.get('starts_at')), _parse_instant(left.get('ends_at'))
    if (place == 'conflicting' or not (left.get('all_day') and right.get('all_day'))
            or not start or not end or end - start <= timedelta(days=1)
            or start != _parse_instant(right.get('starts_at')) or end != _parse_instant(right.get('ends_at'))
            or _contradicting_titles(left, right)):
        return False
    short, long = sorted((left, right), key=lambda row: len(_slot_title_words(row)))
    words, other = _slot_title_words(short), _slot_title_words(long)
    return bool(len(words) >= 2 and words <= other and not ((other - words) & _own_name_words(long))
                and not _held_at(long, words))


def _legacy_story(row: dict) -> bool:
    """A story listing whose precision was never recorded: all_day null,
    starting at local midnight. Its clock is unknown, not midnight."""
    start = _parse_instant(row.get('starts_at'))
    return bool(start and row.get('all_day') is None and '/stories/' in str(row.get('source_url') or '')
                and start.astimezone(PACIFIC_TZ).time().isoformat() == '00:00:00')


def _untimed(row: dict) -> bool:
    return _date_only(row) or _legacy_story(row)


def _quoted_story(left: dict, right: dict, place: str) -> bool:
    """An account's legacy story and its own timed post that day quoting it.

    The story "Joel Mejia Smith: it's been a while..." recorded no clock; the
    post "Film Screening and Live Performance by Joel Mejia Smith" prints the
    story's title in its caption. Date-only teasers keep the stricter
    corroboration in same_event; this covers only stories of unknown precision.
    """
    story, post = (left, right) if _legacy_story(left) else (right, left)
    if (place == 'conflicting' or not _legacy_story(story) or _untimed(post)
            or not _same_account(story, post) or _contradicting_titles(story, post)):
        return False
    days = [_parse_instant(row.get('starts_at')).astimezone(PACIFIC_TZ).date() for row in (story, post)]
    return days[0] == days[1] and _title_phrase_in_description(story, post)


_SEQUENCE = re.compile(r'\b(?:session|part|day|round|week|vol|no)\.?\s*#?\s*(\d+)\b|#\s*(\d+)')
_EDITION = re.compile(r'\b(\d+)(?:st|nd|rd|th)\s+annual\b')


def _contradicting_titles(left: dict, right: dict, *, numbered_once: bool = False) -> bool:
    """Titles that name different occurrences: another year ("Silent Disglo
    2027"), session ("Session 2", "GM #4") or edition ("13th Annual").

    With numbered_once, a meeting or schedule-day label ("GM#1", "Recruitment
    Day 3") that only one title carries is not a contradiction. Different
    numbers still are, and so is a session, part or round of a named occasion
    ("Silent Disglo Session 2")."""
    titles = [str(row.get('title') or '').casefold() for row in (left, right)]
    start = _parse_instant(left.get('starts_at'))
    year = str(start.astimezone(PACIFIC_TZ).year) if start else ''
    years = [set(re.findall(r'\b20\d\d\b', title)) for title in titles]
    # A Fall 2027 application can close in November 2026. Its program year
    # must agree between titles, but need not equal the cutoff's year.
    deadline = all(row.get('content_kind') == 'student_deadline' for row in (left, right))
    if (bool(years[0] and years[1] and years[0] != years[1]) if deadline
            else any(y != year for values in years for y in values)):
        return True
    sequences = [{a or b for a, b in _SEQUENCE.findall(title)} for title in titles]
    editions = [set(_EDITION.findall(title)) for title in titles]
    labels = [{match.group(1) or match.group(2) for match in _SEQUENCE.finditer(title)
               if not re.match(r'(?:session|part|round|week|vol|no)\b', match.group(0))} for title in titles]
    numbered = sequences[0] != sequences[1] and not (
        numbered_once and not (sequences[0] and sequences[1]) and labels == sequences)
    return numbered or bool(editions[0] and editions[1] and editions[0] != editions[1])


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


def _numbered_repeat(left: dict, right: dict, place: str) -> bool:
    """A schedule labels 'Day 1' or '#1'; its matching reminder omits it."""
    if not _same_account(left, right) or place == 'conflicting':
        return False
    titles = [str(row.get('title') or '').casefold() for row in (left, right)]
    sequences = [{a or b for a, b in _SEQUENCE.findall(title)} for title in titles]
    if bool(sequences[0]) == bool(sequences[1]):
        return False
    decoration = re.compile(r'\bday\s+\d+\s*:?|#\s*\d+')
    stripped = [row | {'title': decoration.sub('', title)} for row, title in zip((left, right), titles)]
    if _contradicting_titles(*stripped):
        return False
    forms = [{('talk' if w == 'talks' else w) for w in _title_form(row, other)[0]}
             for row, other in (stripped, stripped[::-1])]
    if not forms[0] or forms[0] != forms[1]:
        return False
    starts = [_parse_instant(row.get('starts_at')) for row in (left, right)]
    if starts[0].astimezone(PACIFIC_TZ).date() != starts[1].astimezone(PACIFIC_TZ).date():
        return False
    if _date_only(left) != _date_only(right):
        return True
    ends = {_parse_instant(row.get('ends_at')) for row in (left, right)} - {None}
    return starts[0] == starts[1] and len(ends) <= 1


def _corrected_schedule(left: dict, right: dict) -> bool:
    """An explicitly revised schedule replaces its own provisional venue."""
    if (not _same_account(left, right) or not _session_row(left) or not _session_row(right)
            or not _specific_slot(left) or not _specific_slot(right)
            or _parse_instant(left.get('starts_at')) != _parse_instant(right.get('starts_at'))
            or _contradicting_titles(left, right)):
        return False
    old, new = sorted((left, right), key=lambda row: max(map(int, _source_media(row)), default=0))
    if not _source_media(old) or max(map(int, _source_media(new))) <= max(map(int, _source_media(old))):
        return False
    a, b = (_title_form(row, other)[0] - {'session'} for row, other in ((old, new), (new, old)))
    ends = {_parse_instant(row.get('ends_at')) for row in (old, new)} - {None}
    corrected = re.search(r'\b(?:new official|updated|revised|corrected)\s+schedule\b',
                          str(new.get('description') or ''), re.I)
    relocated = re.search(r'\b(?:(?:new|updated|revised|corrected)\s+(?:location|room|venue)'
                          r'|(?:location|room|venue)\s+(?:update|change|correction))\b',
                          str(new.get('description') or ''), re.I)
    # "Sisterhood" and "Sisterhood Night" in the same explicitly relocated
    # lineup keep their identity. Other title differences remain significant;
    # session numbers also pass through the contradiction check above.
    titles_match = (a == b or (relocated and (a ^ b) == {'night'} and len(a & b) >= 2)
                    or (corrected and (a ^ b) == {'networking'} and len(a & b) >= 2))
    provisional = re.search(r'\blocation\s+(?:will be|to be)\s+announced\b',
                            str(old.get('description') or ''), re.I)
    return bool(len(a) >= 2 and titles_match and len(ends) <= 1 and (corrected or relocated or provisional))


_CHECK_IN_WINDOW = timedelta(minutes=15)


def _check_in_offset(left: dict, right: dict, place: str) -> bool:
    """One outing posted twice: once at its check-in, once at its departure.

    UCR TAPS's flyer post says 'meet us at Bannockburn Village at 11:50 AM to
    check in'; its monthly carousel says 'we will leave UCR at 12 PM' for the
    same Ride to The Cheech. One account, the same venue and the same specific
    signup link, with starts minutes apart on one day, name one occasion even
    when the titles are worded differently. Sessions of one post never match,
    and nor do different ends.
    """
    if (place != 'same' or not _same_account(left, right) or not _specific_slot(left)
            or not _specific_slot(right) or _contradicting_titles(left, right)):
        return False
    rsvp = _rsvp_identity(left.get('rsvp_url'))
    if not rsvp or rsvp != _rsvp_identity(right.get('rsvp_url')):
        return False
    start, other_start = (_parse_instant(row.get('starts_at')) for row in (left, right))
    ends = {_parse_instant(row.get('ends_at')) for row in (left, right)} - {None}
    if start == other_start or abs(start - other_start) > _CHECK_IN_WINDOW or len(ends) > 1:
        return False
    return bool((_title_form(left, right)[0] & _title_form(right, left)[0]) - _GENERIC_WORDS)


def _video_cover(row: dict) -> bool:
    """Whether the row's image is a frame of a video (a reel), not a flyer."""
    return row.get('image_is_video') is True and bool(row.get('image_url'))


def _post_number(row: dict) -> int:
    """The newest post a row was published from; media IDs rise with time."""
    return max(map(int, _source_media(row)), default=0)


def _follow_up(row: dict, original: dict) -> bool:
    """A reel the account posted after its flyer announcement of one event.

    Clubs announce an event with a flyer, then post reels as it nears. A reel
    is read from its caption and one frame of the video. It can add a detail
    the announcement lacked, but its cover is no flyer and its caption is
    promotion, so the announcement stays the listing. A line in a schedule
    post is not that announcement: the reel about the one event names it
    better, and only takes the schedule's image (merge_duplicates).
    """
    return (_video_cover(row) and bool(original.get('image_url')) and not _video_cover(original)
            and not _session_row(original)
            and _same_account(row, original) and 0 < _post_number(original) < _post_number(row))


# A caption saying the date or time changed. "New time added" and "new time
# slot" announce another session, not a change, and "new day" is too often a
# title ("Spider-Man: Brand New Day").
_TIME_CHANGE = re.compile(
    r"\b(?:re-?schedul\w+|postpon\w+|pushed\s+(?:back|up)"
    r"|(?:time|date|day)\s+(?:change|update|correction)\w*"
    r"|(?:change|update|correction)\s+(?:of|in|to)\s+(?:the\s+|our\s+)?(?:time|date|day)"
    r"|(?:updated|changed|corrected|revised)\s+(?:time|date|day)"
    r"|new\s+(?:time|date)(?!\s+(?:slot|option|added|available|night)|s\b)"
    r"|(?:moved|moving|changed|pushed)\s+(?:\w+\s+){0,3}?to\s+(?:next\s+|this\s+)?"
    r"(?:(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)(?:day)?\b"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d|\d{1,2}(?::\d\d)?\s*[ap]\.?m\b))",
    re.I)


def _announces_change(row: dict) -> bool:
    return bool(_TIME_CHANGE.search(str(row.get('description') or '')))


def _retimed(old: dict, new: dict) -> bool:
    """One event that its account's later post puts at another date or time.

    The titles name one event, and apart from when it happens the rules call
    the pair one event. That alone proves nothing (a weekly meeting repeats
    its title), so callers also need the later post to say the time changed,
    or an admin to agree. A date-only teaser and its timed announcement are
    not a change; same_event relates those itself.
    """
    starts = [_parse_instant(row.get('starts_at')) for row in (old, new)]
    if (None in starts or starts[0] == starts[1] or not _same_account(old, new)
            or not 0 < _post_number(old) < _post_number(new) or _session_row(new)
            or _date_only(old) != _date_only(new) or _legacy_story(old) or _legacy_story(new)
            or _contradicting_titles(old, new)):
        return False
    # Given one time, any two listings of an account in one room match by
    # their slot. The titles must agree on their own.
    a, b = _title_form(old, new)[0], _title_form(new, old)[0]
    if not a or not (a == b or ((a <= b or b <= a) and len((a & b) - _GENERIC_WORDS) >= 2)):
        return False
    return same_event(old | {key: new.get(key) for key in ('starts_at', 'ends_at', 'all_day')}, new)


def _rescheduled(left: dict, right: dict) -> bool:
    """A later post that says the event moved to another time that day.

    ASPB's flyer says doors at 6 PM; its reel two days out says "TIME CHANGE:
    doors now open at 7". One account, one title and the caption's own word
    for it make the reel a correction rather than a second showing. A move to
    another day is left to an admin (retimed_candidates): the same title on
    another day is usually the next meeting.
    """
    starts = [_parse_instant(row.get('starts_at')) for row in (left, right)]
    if (None in starts or starts[0] == starts[1]
            or starts[0].astimezone(PACIFIC_TZ).date() != starts[1].astimezone(PACIFIC_TZ).date()):
        return False
    old, new = sorted((left, right), key=_post_number)
    return not _date_only(new) and _announces_change(new) and _retimed(old, new)


def _supersedes(new: dict, old: dict) -> bool:
    """Whether new's date and time replace old's: a corrected deadline or a
    rescheduled event, from a later post."""
    starts = [_parse_instant(row.get('starts_at')) for row in (old, new)]
    if None in starts or starts[0] == starts[1] or not 0 < _post_number(old) < _post_number(new):
        return False
    return _corrected_deadline(old, new) or _rescheduled(old, new)


def _fills_time(new: dict, old: dict) -> bool:
    """A reel that gives the time of day its date-only announcement left out."""
    starts = [_parse_instant(row.get('starts_at')) for row in (old, new)]
    return (None not in starts and _follow_up(new, old) and _date_only(old) and not _untimed(new)
            and starts[0].astimezone(PACIFIC_TZ).date() == starts[1].astimezone(PACIFIC_TZ).date())


def same_event(left: dict, right: dict) -> bool:
    """Match corroborated announcements using shared title, owner and place rules."""
    start, other_start = (_parse_instant(r.get('starts_at')) for r in (left, right))
    if start is None or other_start is None or left.get('content_kind') != right.get('content_kind'):
        return False
    # Sessions of one post share its caption, link and flyer, and can share a
    # start. They are still different events.
    if _sibling_sessions(left, right):
        return False
    # An open house can offer a continuous resource fair and separately
    # registered tour sessions. Sharing the venue and first start is not a
    # reason to replace the fair's hours with the morning tour's hours.
    titles = [str(row.get('title') or '').casefold() for row in (left, right)]
    for fair, tour in (titles, titles[::-1]):
        if ('resource fair' in fair and 'resource fair' not in tour
                and ('guided tour' in tour or ('open house' in tour
                     and re.search(r'\b(?:morning|afternoon)\s+session\b', tour)))):
            return False
    # A feed row and a retired story reshare are one post. The two parses may
    # disagree on room or end time.
    if start == other_start and (_source_media(left) & _source_media(right)):
        return True
    place = _same_place(left, right)
    if (_numbered_repeat(left, right, place) or _corrected_schedule(left, right)
            or _unnumbered_repeat(left, right, place)):
        return True
    if _contradicting_titles(left, right):
        return False
    if (_same_slot_event(left, right, place) or _shared_occasion_name(left, right, place)
            or (start != other_start and _corrected_deadline(left, right))):
        return True
    # Patterns from the admin's September 26 review decisions.
    if (_schedule_superseded(left, right) or _same_multiday_span(left, right, place)
            or _quoted_story(left, right, place) or _check_in_offset(left, right, place)
            or _rescheduled(left, right)):
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
        # A deadline's season qualifier names no other cutoff: AXO's "Fall
        # recruitment registration deadline" at 5 PM and its "Recruitment
        # registration deadline" that day close one registration.
        seasonless = ((lambda words: words - _SEASONS) if left.get('content_kind') == 'student_deadline'
                      and not (a & _SEASONS and b & _SEASONS) else None)
        exact_repeat = same_account and bool(distinctive) and (
            a == b or bool(seasonless and seasonless(a) == seasonless(b)))
        # The timed announcement quotes the teaser's whole title: the teaser
        # named this occasion before its time (and possibly venue) was out.
        # Another account also needs the same venue and a distinctive name.
        teaser_words = a if teaser is left else b
        quoted = (_title_phrase_in_description(teaser, timed) and (
            (place == 'same' and len(distinctive) >= 3)
            or (same_account and not _place_words(teaser) and len(distinctive) >= 2
                and teaser_words <= (b if teaser is left else a))))
        quoted = quoted or (same_account and not _place_words(teaser) and len(distinctive) >= 2
                            and _title_phrase_in_description(timed, teaser))
        return bool(quoted or (
            len(common) >= (2 if exact_repeat else 3) and distinctive
            and _teaser_titles(*((seasonless(a), seasonless(b)) if seasonless else (a, b)), left, right)
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


def prefer_repost_source(winner: dict, rows: list[dict], *, reviews: Reviews = Reviews(),
                         preserve_identity: bool = True) -> dict:
    """Prefer corrected reposts; retain the listing identity during republication.

    Caption length is not freshness. Compare feed permalink media IDs (not the
    listing ID, which may already retain an older identity after a repair).
    This only uses collected evidence; it does not check Instagram availability.
    """
    if (winner.get('is_locked') or reviews.kept(winner['id'])
            or any(reviews.kept(event_id) == winner['id'] for event_id in reviews.merged)):
        return winner

    def media(row):
        return max(map(int, _source_media({'source_url': row.get('source_url')})), default=0)

    current = media(winner)
    if not current or imported_row_kind(winner) != 'instagram':
        return winner
    candidates = []
    for row in rows:
        if (media(row) <= current or imported_row_kind(row) != 'instagram'
                or not _same_account(winner, row)
                or _parse_instant(winner.get('starts_at')) != _parse_instant(row.get('starts_at'))
                or _date_only(winner) != _date_only(row)
                or bool(winner.get('all_day')) != bool(row.get('all_day'))
                or _session_row(winner) != _session_row(row)
                or reviews.kept(row['id']) or reviews.judged_distinct([winner, row])
                or not same_event(winner, row)):
            continue
        # A newer teaser must not replace the useful announcement. Length is
        # deliberately absent: removing obsolete TBA boilerplate is an upgrade.
        # Nor may a reel: its cover would replace the flyer (see _follow_up).
        if (not str(row.get('description') or '').strip() or _follow_up(row, winner)
                or any(winner.get(key) and not row.get(key) for key in
                       ('ends_at', 'image_url', 'rsvp_url', 'rsvp_required', 'has_free_food'))
                or (_place_words(winner) and not _host_venue(winner)
                    and (not _place_words(row) or _host_venue(row)))):
            continue
        candidates.append(row)
    # A vague original cannot choose between conflicting corrected listings.
    if not candidates or any(not same_event(a, b) for i, a in enumerate(candidates)
                             for b in candidates[i + 1:]):
        return winner
    source = max(candidates, key=lambda row: (media(row), row['id']))
    if not preserve_identity:
        return source
    return adopt_source(merge_duplicates(winner, [winner, source]), source)


def adopt_source(listing: dict, source: dict) -> dict:
    """The listing, now linked to and described by another post of its event.

    The permalink, caption and flyer always come from the source, even when it
    has none: they describe that one post. A corrected venue travels with its
    source too. An omitted venue, TBA or the host center's own name corrects
    nothing, so the listing's own venue stays.
    """
    adopted = dict(listing)
    for key in ('source_url', 'description', 'image_url'):
        if key in source:
            adopted[key] = source[key]
    if 'image_url' in source and ('image_is_video' in source or 'image_is_video' in adopted):
        adopted['image_is_video'] = source.get('image_is_video')
    if _place_words(source) and not _host_venue(source):
        adopted['location'] = source['location']
    return adopted


# Words every application or signup deadline shares; they name no program.
_DEADLINE_BOILERPLATE = frozenset('application applications deadline registration recruitment program due'.split())


def review_candidates(rows: list[dict], *, now: datetime | None = None,
                      reviews: Reviews = Reviews()) -> list[tuple[dict, dict]]:
    """Upcoming pairs that look alike but no rule merged, for human review.

    The rules merge only corroborated repeats; a new kind of repost (another
    wording, venue or account) first appears here instead of silently on the
    site. Pairs overlap on one day and either come from one account at one
    start, or share two distinctive title words. A reel that gives its
    account's announcement another time that day, without saying the time
    changed, is asked about too. A pair an admin already judged different is
    not asked about again.
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
            old, new = sorted((left, right), key=_post_number)
            reel = _follow_up(new, old)
            if ((other_start > end and not reel) or left.get('content_kind') != right.get('content_kind')
                    or _sibling_sessions(left, right) or reviews.judged_distinct([left, right])
                    or same_event(left, right)):
                continue
            if reel and _retimed(old, new):
                pairs.append((left, right))
                continue
            if other_start > end:
                continue
            shared = (_slot_title_words(left) & _slot_title_words(right)) - _DEADLINE_BOILERPLATE
            if (_same_account(left, right) and start == other_start and _specific_slot(left)
                    and _specific_slot(right)) or len(shared) >= 2:
                pairs.append((left, right))
    return pairs


# How far a rescheduled event is looked for. Postponements run days or a
# couple of weeks; beyond that the same title is the next edition.
_RETIMED_WINDOW = timedelta(days=21)


def retimed_candidates(rows: list[dict], *, now: datetime | None = None,
                       reviews: Reviews = Reviews()) -> list[tuple[dict, dict]]:
    """Upcoming pairs where an account's later post moves its event to another day.

    The later post must say so ("rescheduled", "postponed", "new date") and
    otherwise match the earlier listing, which must carry a word that names
    it: "General Meeting" on two Wednesdays is two meetings. Even then the
    pair is only asked about, never merged. An admin who agrees takes the
    new date in the merge.
    """
    by_account: dict[str, list[dict]] = {}
    for row in rows:
        start = _parse_instant(row.get('starts_at'))
        if start and _account(row) and not (now and (_parse_instant(row.get('ends_at')) or start) < now):
            by_account.setdefault(_account(row), []).append(row)
    pairs = []
    for listings in by_account.values():
        listings.sort(key=lambda row: (_post_number(row), row['id']))
        for i, old in enumerate(listings):
            for new in listings[i + 1:]:
                starts = [_parse_instant(row['starts_at']).astimezone(PACIFIC_TZ) for row in (old, new)]
                if (starts[0].date() == starts[1].date() or abs(starts[0] - starts[1]) > _RETIMED_WINDOW
                        or old.get('content_kind') != new.get('content_kind')
                        or not _announces_change(new)
                        or not (_slot_title_words(old) & _slot_title_words(new))
                        or reviews.judged_distinct([old, new]) or same_event(old, new)
                        or not _retimed(old, new)):
                    continue
                pairs.append((old, new))
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
    ambiguous = {row['id'] for row in candidates if _untimed(row) and len({
        _parse_instant(other.get('starts_at')) for other in index.peers(row)
        if not _untimed(other) and same_event(row, other)
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
        # A corrected deadline replaces its old date rather than bridging it,
        # and a check-in time and its departure are one outing.
        timed = [r for r in [row, *(r for group in matches for r in group)] if not _untimed(r)]
        if len({_parse_instant(r.get('starts_at')) for r in timed}) > 1 and not all(
                _corrected_deadline(a, b) or _check_in_offset(a, b, _same_place(a, b)) or _rescheduled(a, b)
                for i, a in enumerate(timed) for b in timed[i + 1:]
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
        # Rows on different days are a corrected deadline, and a post that
        # says the time changed is a rescheduling: the newest post's date and
        # time are the current ones. A reel after the announcement never
        # becomes the listing; merge_duplicates gives the announcement the
        # time the reel adds or corrects.
        revised = (len({_parse_instant(r['starts_at']).astimezone(PACIFIC_TZ).date() for r in live}) > 1
                   or any(_rescheduled(a, b) for i, a in enumerate(live) for b in live[i + 1:]))
        reels = {r['id'] for r in live if any(_follow_up(r, other) for other in live)}
        winner = max(live, key=lambda r: (r['id'] not in forced, bool(r.get('is_locked')),
                     r['id'] not in reels, not _date_only(r),
                     kinds[r['id']] == 'instagram',
                     _named_organizer(r, live), not _session_row(r),
                     max(map(int, _source_media(r)), default=0) if revised else 0, _row_score(r)))
        winner = prefer_repost_source(winner, live, reviews=reviews, preserve_identity=False)
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


def _later_times(winner: dict, live: list[dict]) -> dict:
    """The date and time a later post of the listing's account gives it.

    A post that corrects or reschedules the listing replaces its time; the
    newest such post is current. Otherwise reels that agree on a time of day
    fill in a date-only listing. Empty when no post does either.
    """
    others = [r for r in live if r['id'] != winner['id']]
    donors = [r for r in others if _supersedes(r, winner)]
    if not donors:
        donors = [r for r in others if _fills_time(r, winner)]
        if len({_parse_instant(r.get('starts_at')) for r in donors}) != 1:
            return {}
    donor = max(donors, key=lambda r: (_post_number(r), bool(r.get('ends_at')), r['id']))
    return {key: donor.get(key) for key in ('starts_at', 'ends_at', 'all_day')}


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
    retimed = _later_times(winner, live)
    merged.update(retimed)
    # A corrected deadline's superseded date must not stretch its end.
    start = _parse_instant(merged.get('starts_at'))
    same_day = [r for r in live if start and (_parse_instant(r.get('starts_at')) or start)
                .astimezone(PACIFIC_TZ).date() == start.astimezone(PACIFIC_TZ).date()]
    if retimed:
        # Nor may the time a later post replaced supply the end.
        same_day = [r for r in same_day if _parse_instant(r.get('starts_at')) == start]
    for key in ('ends_at', 'rsvp_url', 'location'):
        # A placeholder (TBA, Room TBD) or bare campus location names no venue.
        vague = key == 'location' and (_host_venue(winner) or not _place_words(winner))
        if not merged.get(key) or vague:
            pool = signup_rows if key == 'rsvp_url' else same_day if key == 'ends_at' else live
            options = {r[key] for r in pool if r.get(key)
                       and not (key == 'location' and (_host_venue(r) or not _place_words(r)))
                       and not (key == 'ends_at' and _date_only(r) and not _date_only(merged))}
            if len(options) == 1:
                merged[key] = options.pop()
    # A missing flyer comes from the one duplicate that has one. A reel's
    # cover frame is no flyer either: the account's earliest still image
    # replaces it, or the one still a partner posted.
    if not merged.get('image_url') or _video_cover(merged):
        stills = sorted((r for r in live if r.get('image_url') and not _video_cover(r)),
                        key=lambda r: (_post_number(r), r['id']))
        own = [r for r in stills if _same_account(r, winner)] if merged.get('image_url') else []
        pool = own[:1] or stills or ([] if merged.get('image_url') else [r for r in live if r.get('image_url')])
        if len({r['image_url'] for r in pool}) == 1:
            merged['image_url'] = pool[0]['image_url']
            if 'image_is_video' in pool[0] or 'image_is_video' in merged:
                merged['image_is_video'] = pool[0].get('image_is_video')
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
    # post simply contributes nothing here. A rebuilt ID embeds its post's media
    # ID, so only a post a deleted ID names, or whose recorded IDs were deleted,
    # can match; skip reading and rebuilding every other post.
    deleted_media = {match.group(2) for event_id in deleted if (match := POST_EVENT_ID.fullmatch(event_id))}
    # Only these sources can match, so read just them, not every assessment.
    registry = publication.load_registry(
        keys=[f"instagram:post:{media_id}" for media_id in deleted_media],
        event_ids=deleted, known_event_ids=deleted)
    import extract_posts as igposts
    import post_archive
    for record in post_archive.iter_local_posts():
        saved = registry.get(f"instagram:post:{record['media_id']}")
        if saved is None or (str(record['media_id']) not in deleted_media and not deleted & {
                *(saved.get('event_ids') or []), *(saved.get('known_event_ids') or [])}):
            continue
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
        # sort_at is generated from the times; Postgres rejects any write to it.
        changes = {key: value for key, value in row.items()
                   if key != 'sort_at' and value != before.get(key)}
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
    moved = retimed_candidates(list(canonical.values()), now=datetime.now(timezone.utc), reviews=reviews)
    for old, new in moved:
        log.warning('Possible rescheduled event for review: %s %r and %s %r (@%s)',
                    old['id'], old.get('title'), new['id'], new.get('title'), new.get('host_handle'))
    queue_duplicate_reviews([(left['id'], right['id']) for left, right in [*suspects, *moved]], queue)
    log.info('%d possible duplicates queued for admin review', len(suspects))
    log.info('%d possible reschedulings queued for admin review', len(moved))
    if notify:
        sent = notify_free_food_events(canonical.values())
        log.info('Sent %d free food Discord notifications', sent)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
