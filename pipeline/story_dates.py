"""Date and time reasoning for Instagram story flyers.

Everything here answers one question: what day and time does the *source text*
support? Callers assemble rows; this module decides what the flyer actually
said. Model timestamps may be aligned to that evidence, but confidence and
API status cannot establish it.

There is one date vocabulary (`_scan_printed_dates`) and two policies over it:

* `override_dates` is deliberately narrow. The wall-time override rebuilds a
  timestamp from scratch, so it reads only "Month Day" without a printed year
  and only Pacific wall time. Widening it changes which flyers it claims.
* `evidence_dates` is broad. It only has to establish that source text pinned
  down a calendar day, so it accepts any notation that does so.

Keeping both as filters over the same scanner is what stops the two from
drifting into parallel date dialects.
"""
from __future__ import annotations

import re
from datetime import datetime, time, timedelta, timezone
from typing import Any, Iterable, Iterator
from zoneinfo import ZoneInfo

PACIFIC_TZ = ZoneInfo("America/Los_Angeles")

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

# --- date notations -------------------------------------------------------
_OCR_DATE_RE = re.compile(
    r"\b("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?|tember)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?"
    r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b",
    re.IGNORECASE,
)
_OCR_DAY_MONTH_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(_MONTHS) + r")\b",
    re.IGNORECASE,
)
_OCR_NUMERIC_DATE_RE = re.compile(
    r"(?<![\w/.$])(?:\d{4}-)?(\d{1,2})([/.-])(\d{1,2})"
    r"(?:\2(\d{4}|\d{2}))?(?![\w/])"
)
# Two slash dates across a range dash corroborate each other: "10/8-10/11" is
# a run of days, never a pair of fractions.
_OCR_NUMERIC_RANGE_RE = re.compile(
    r"(?<![\w/.$])(\d{1,2})/(\d{1,2})\s*(?:[-\u2013\u2014]|to|thru|through)\s*"
    r"(\d{1,2})/(\d{1,2})(?![\w/])",
    re.IGNORECASE,
)

# --- immediacy ------------------------------------------------------------
# Immediacy words bind the event to posted_at rather than unlocking a model
# timestamp, so they need no corroborating time. "now"/"rn" claim the posting
# instant; the rest claim a calendar day and leave the time to extraction.
_OCR_NOW_RE = re.compile(r"\b(?:now|rn)\b", re.IGNORECASE)
# "apply now" and "applications are now open" are calls to action, not claims
# that an event is under way, and on club flyers they outnumber the real ones.
_CTA_BEFORE_NOW_RE = re.compile(
    r"\b(?:appl(?:y|ies|ication)s?|register|registration|sign\s*ups?|signup|"
    r"donate|enroll|rsvp|order|shop|buy|vote|submit|nominate|follow|dm|"
    r"available|are|open)\b(?:\s+\w+){0,2}\s*$",
    re.IGNORECASE,
)
_BOOKING_CTA_BEFORE_NOW_RE = re.compile(
    r"\b(?:book|reserve|claim|secure|grab|purchase|schedule)\b"
    r"(?:\s+\w+){0,2}\s*$|\bjoin\s*$",
    re.IGNORECASE,
)
_CTA_AFTER_NOW_RE = re.compile(
    r"\s*(?:accepting|available|open|hiring|recruiting)\b",
    re.IGNORECASE,
)
_OCR_IMMEDIATE_DAY_RE = re.compile(
    r"\b(?:today|tonight|tomorrow)\b", re.IGNORECASE
)
_DAY_CTA_RE = re.compile(
    r"\b(?:apply|applications?|register|registration|sign\s*ups?|donate|enroll|"
    r"rsvp|order|shop|buy|vote|submit|nominate|follow|dm)\b(?:\s+\w+){0,2}\s*$",
    re.IGNORECASE,
)
# A bare weekday is prose ("happy Friday", "Monday motivation") as often as it
# is a date, so it only counts as evidence next to a clock time.
_OCR_WEEKDAY_RE = re.compile(
    r"\b(?:mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:rs(?:day)?)?|"
    r"fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b",
    re.IGNORECASE,
)
_OCR_CLOCK_TIME_RE = re.compile(
    r"\b\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?|\b\d{1,2}:\d{2}\b|\bnoon\b|\bmidnight\b",
    re.IGNORECASE,
)

# --- wall-time override ---------------------------------------------------
# The override only understands dates without a printed year and Pacific wall
# time without an explicit timezone. Leave richer expressions to extraction.
_OCR_EXPLICIT_YEAR_RE = re.compile(r"\s*,?\s*(?:19|20)\d{2}\b")
_OCR_TIMEZONE_RE = re.compile(
    r"\b\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?\s*[\[(]?\s*"
    r"(?:[PECM][SD]?T|UTC|GMT|Pacific|Eastern|Central|Mountain)\b",
    re.IGNORECASE,
)
_OCR_TIME_RANGE_RE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)"
    r"(?:\s*(?:[-–—]|to)\s*|\s+)"
    r"(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)\b",
    re.IGNORECASE,
)
# Compact ranges like "1-2 pm" apply the trailing meridiem to both endpoints.
_OCR_COMPACT_TIME_RANGE_RE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(?:[-–—]|to)\s*"
    r"(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)\b",
    re.IGNORECASE,
)

# Schedule flyers lay out multiple dates or time slots, while the extractor can
# emit only one event row. Skip clear multi-event schedules instead of
# publishing a made-up range that collapses every slot together.
_GRID_MIN_DISTINCT_DATES = 3
_GRID_MIN_TIME_RANGES = 3
_SCHEDULE_HINT_RE = re.compile(r"\b(?:schedule|hours|practice|times)\b", re.IGNORECASE)
_STALE_EVENT_GRACE = timedelta(days=1)

_MONTH_NAME = "month_name"
_DAY_MONTH = "day_month"
_NUMERIC = "numeric"
_NUMERIC_BARE = "numeric_bare"
_LABELED = "labeled"


def _labeled_date(text: str) -> tuple[int, int, int, tuple[int, int]] | None:
    """Read separate month/day/year tiles only with their explicit labels."""
    labels = re.search(r"\bMONTH\s+DAY\s+YEAR\b", text, re.IGNORECASE)
    if not labels:
        return None
    numbers = list(re.finditer(r"(?m)^\s*(\d{1,4})\s*$", text[max(0, labels.start()-100):labels.start()]))
    if len(numbers) != 3:
        return None
    month, day, year = (int(m.group(1)) for m in numbers)
    if year < 100:
        year += 2000
    return month, day, year, (max(0, labels.start()-100), labels.end())


def normalize_timestamptz(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat()


def local_posted_at(raw: dict[str, Any]) -> datetime | None:
    """When the story was posted, in Pacific wall time."""
    posted_at = raw.get("posted_at")
    if not isinstance(posted_at, str):
        return None
    text = posted_at.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(PACIFIC_TZ)


def _scan_printed_dates(text: str) -> Iterator[tuple[str, int, int, tuple[int, int]]]:
    """Every date-shaped token in the text, tagged with its notation and span.

    This is the single vocabulary the policies below filter. The span lets a
    policy read a token's neighbours (see `_bare_date_is_corroborated`).
    Calendar validity is not checked here so that the override can keep
    applying its own.
    """
    labeled = _labeled_date(text)
    if labeled:
        month, day, _, span = labeled
        yield _LABELED, month, day, span
    for match in _OCR_DATE_RE.finditer(text):
        yield (
            _MONTH_NAME,
            _MONTHS[match.group(1).lower().rstrip(".")],
            int(match.group(2)),
            match.span(),
        )
    for match in _OCR_DAY_MONTH_RE.finditer(text):
        yield (
            _DAY_MONTH,
            _MONTHS[match.group(2).lower()],
            int(match.group(1)),
            match.span(),
        )
    for match in _OCR_NUMERIC_DATE_RE.finditer(text):
        if match.group(4) or re.match(r"\d{4}-", match.group()):
            form = _NUMERIC
        elif match.group(2) in {"/", "."}:
            form = _NUMERIC_BARE
        else:
            # Without a year "1-2" is a time range and "5.62" a decimal.
            continue
        yield form, int(match.group(1)), int(match.group(3)), match.span()


def _is_calendar_day(month: int, day: int) -> bool:
    try:
        # A leap year keeps February 29 valid; the year itself is irrelevant.
        datetime(2000, month, day)
    except ValueError:
        return False
    return True


def override_dates(text: str) -> set[tuple[int, int]]:
    """Dates in the one notation the wall-time override can safely rebuild."""
    return {
        (month, day)
        for form, month, day, _ in _scan_printed_dates(text)
        if form is _MONTH_NAME
    }


def _bare_date_is_corroborated(text: str, span: tuple[int, int]) -> bool:
    """Whether a bare "5/28" here reads as a date rather than a fraction.

    Any one of three neighbours settles it: a clock time on the flyer, a second
    slash date across a range dash ("recruitment is 10/8-10/11"), or a weekday
    printed beside it ("signups close Thursday (6/11)"). A fraction or a room
    number keeps none of that company, and a flyer that prints only a date
    range is still a flyer that named its days.
    """
    start, end = span
    if re.search(r"\b(?:room|suite|building|price|cost|reading)\s*$", text[max(0, start-20):start], re.IGNORECASE):
        return False
    if re.match(r"\s*(?:price|off|cups?|tbsp|tsp|inches)\b", text[end:], re.IGNORECASE):
        return False
    if _OCR_CLOCK_TIME_RE.search(text):
        return True

    for match in _OCR_NUMERIC_RANGE_RE.finditer(text):
        if match.start() <= start and end <= match.end() and all(
            _is_calendar_day(int(month), int(day))
            for month, day in (
                (match.group(1), match.group(2)),
                (match.group(3), match.group(4)),
            )
        ):
            return True

    # A nearby greeting ("Happy Friday! 1/2 price boba") is not a date label.
    for weekday in _OCR_WEEKDAY_RE.finditer(text):
        if weekday.end() <= start:
            between = text[weekday.end():start]
        elif end <= weekday.start():
            between = text[end:weekday.start()]
        else:
            continue
        if len(between) <= 8 and re.fullmatch(r"[\s,().]*", between):
            return True
    return False


def evidence_dates(text: str) -> set[tuple[int, int]]:
    """Calendar days the source text actually pins down.

    Any notation counts, but a bare "5/28" is as often a fraction or a room
    number as a date, so it counts only when a neighbour corroborates it.
    """
    return {
        (month, day)
        for form, month, day, span in _scan_printed_dates(text)
        if _is_calendar_day(month, day)
        and (form is not _NUMERIC_BARE or _bare_date_is_corroborated(text, span))
    }


def single_override_date(text: str) -> tuple[int, int] | None:
    """The one date the override may use, or None when the flyer is ambiguous."""
    dates = override_dates(text)
    if len(dates) != 1:
        return None
    return next(iter(dates))


def source_date_texts(
    raw: dict[str, Any],
    cached: dict[str, Any],
) -> Iterable[str]:
    """OCR and caption text with handles and links stripped.

    Model output and posting metadata are deliberately excluded: they are what
    the date evidence is meant to check, not a source of it.
    """
    for value in (cached.get("ocr_text"), raw.get("caption")):
        if isinstance(value, str):
            yield re.sub(r"https?://\S+|www\.\S+|@[\w.]+", "", value)


def claims_happening_now(text: str, *, legacy: bool = False) -> bool:
    """True when "now"/"rn" says an event is under way, not "apply now"."""
    for match in _OCR_NOW_RE.finditer(text):
        before = text[max(0, match.start() - 40) : match.start()]
        after = text[match.end() : match.end() + 20]
        if _CTA_BEFORE_NOW_RE.search(before) or _CTA_AFTER_NOW_RE.match(after):
            continue
        if not legacy and _BOOKING_CTA_BEFORE_NOW_RE.search(before):
            continue
        return True
    return False


def _immediate_day(text: str, *, legacy: bool = False) -> str | None:
    for match in _OCR_IMMEDIATE_DAY_RE.finditer(text):
        before = text[max(0, match.start() - 40):match.start()]
        if not legacy and (
            _DAY_CTA_RE.search(before)
            or _BOOKING_CTA_BEFORE_NOW_RE.search(before)
        ):
            continue
        return match.group().lower()
    return None


def has_source_date(raw: dict[str, Any], cached: dict[str, Any]) -> bool:
    """Minimum date-evidence gate, independent of model confidence or API status.

    Source text must print a calendar day, claim immediacy that binds to
    posted_at, or corroborate a bare weekday with a clock time. This establishes
    that source text supplies a date, not that every extracted detail is
    correct.
    """
    has_posting_context = local_posted_at(raw) is not None
    for text in source_date_texts(raw, cached):
        if evidence_dates(text):
            return True
        if not has_posting_context:
            continue
        if claims_happening_now(text) or _immediate_day(text):
            return True
        if _OCR_WEEKDAY_RE.search(text) and _OCR_CLOCK_TIME_RE.search(text):
            return True
    return False


def immediate_event_range(
    raw: dict[str, Any],
    cached: dict[str, Any],
    llm_starts_at: str | None,
    llm_ends_at: str | None,
    *,
    legacy: bool = False,
) -> tuple[str, str | None] | None:
    """Bind an immediacy story to the day its source text actually claims.

    "now"/"rn" mean the posting instant, so they replace the model's clock,
    which commonly reports posted_at's UTC value as local time. "today",
    "tonight" and "tomorrow" fix only the calendar day and leave the time to
    extraction. Returning None means source text made no immediacy claim and
    the model's timestamp stands.

    `legacy` reconstructs the pre-fix timestamp only to retire old row IDs;
    it must never supply a new event's date.
    """
    posted_at = local_posted_at(raw)
    if posted_at is None or not llm_starts_at:
        return None

    claims_now = False
    claimed_day: str | None = None
    for text in source_date_texts(raw, cached):
        # A printed date outranks a passing "apply now" or "open today".
        printed_dates = evidence_dates(text) if not legacy else {
            (month, day) for form, month, day, _ in _scan_printed_dates(text)
            if _is_calendar_day(month, day)
            and (form != _NUMERIC_BARE or _OCR_CLOCK_TIME_RE.search(text))
        }
        if printed_dates:
            return None
        claims_now = claims_now or claims_happening_now(text, legacy=legacy)
        claimed_day = claimed_day or _immediate_day(text, legacy=legacy)

    start = datetime.fromisoformat(llm_starts_at).astimezone(PACIFIC_TZ)
    end = (
        datetime.fromisoformat(llm_ends_at).astimezone(PACIFIC_TZ)
        if llm_ends_at
        else None
    )

    if claimed_day is not None:
        # Whole-day arithmetic on a Pacific-local datetime keeps the wall time
        # across a DST boundary, which is what "same time, other day" means.
        shift = (
            posted_at.date()
            + timedelta(days=1 if claimed_day == "tomorrow" else 0)
            - start.date()
        )
        start += shift
        if end is not None:
            end += shift
        # Midnight is the model's "time unknown"; on the posting day itself the
        # post time is the better estimate.
        if start.time() == time(0, 0) and start.date() == posted_at.date():
            start = posted_at
    elif claims_now:
        start = posted_at
    else:
        return None

    if end is not None and end <= start:
        end = None
    return start.astimezone(timezone.utc).isoformat(), (
        end.astimezone(timezone.utc).isoformat() if end is not None else None
    )


def _parse_ampm_time(
    hour: str,
    minute: str | None,
    meridiem: str,
) -> tuple[int, int] | None:
    hour_value = int(hour)
    minute_value = int(minute or "0")
    if not 1 <= hour_value <= 12 or not 0 <= minute_value <= 59:
        return None

    normalized = meridiem.lower().replace(".", "")
    if normalized == "am":
        hour_value = 0 if hour_value == 12 else hour_value
    elif normalized == "pm":
        hour_value = hour_value if hour_value == 12 else hour_value + 12
    else:
        return None
    return hour_value, minute_value


def time_range(ocr_text: str) -> tuple[tuple[int, int], tuple[int, int]] | None:
    full_matches = list(_OCR_TIME_RANGE_RE.finditer(ocr_text))
    compact_matches = list(_OCR_COMPACT_TIME_RANGE_RE.finditer(ocr_text))
    if len(full_matches) + len(compact_matches) != 1:
        return None

    if full_matches:
        match = full_matches[0]
        start = _parse_ampm_time(match.group(1), match.group(2), match.group(3))
        end = _parse_ampm_time(match.group(4), match.group(5), match.group(6))
    else:
        match = compact_matches[0]
        start = _parse_ampm_time(match.group(1), match.group(2), match.group(5))
        end = _parse_ampm_time(match.group(3), match.group(4), match.group(5))
    if start is None or end is None:
        return None
    return start, end


def time_range_count(ocr_text: str) -> int:
    return len(list(_OCR_TIME_RANGE_RE.finditer(ocr_text))) + len(
        list(_OCR_COMPACT_TIME_RANGE_RE.finditer(ocr_text))
    )


def local_event_range(
    raw: dict[str, Any],
    cached: dict[str, Any],
) -> tuple[str, str] | None:
    """Rebuild a start/end from OCR wall time, or None when it cannot be trusted."""
    ocr_text = cached.get("ocr_text")
    if not isinstance(ocr_text, str):
        return None

    if any(
        _OCR_EXPLICIT_YEAR_RE.match(ocr_text, date.end())
        for date in _OCR_DATE_RE.finditer(ocr_text)
    ) or _OCR_TIMEZONE_RE.search(ocr_text):
        return None

    posted_at = local_posted_at(raw)
    date_parts = single_override_date(ocr_text)
    times = time_range(ocr_text)
    if posted_at is None or date_parts is None or times is None:
        return None

    month, day = date_parts
    (start_hour, start_minute), (end_hour, end_minute) = times
    try:
        start = datetime(
            posted_at.year,
            month,
            day,
            start_hour,
            start_minute,
            tzinfo=PACIFIC_TZ,
        )
        end = datetime(
            posted_at.year,
            month,
            day,
            end_hour,
            end_minute,
            tzinfo=PACIFIC_TZ,
        )
    except ValueError:
        return None

    # A December story advertising January omits the year but means next year.
    if start < posted_at - timedelta(days=180):
        try:
            start = start.replace(year=start.year + 1)
            end = end.replace(year=end.year + 1)
        except ValueError:
            return None

    if end <= start:
        if end_hour == 0 and end_minute == 0 and start_hour >= 12:
            end += timedelta(days=1)
        else:
            return None
    return start.astimezone(timezone.utc).isoformat(), end.astimezone(
        timezone.utc
    ).isoformat()


def align_printed_dates(
    raw: dict[str, Any], cached: dict[str, Any], starts_at: str, ends_at: str | None,
) -> tuple[str, str | None] | None:
    """Make the model's day agree with printed evidence, including single times.

    Multiple printed days cannot pick an unrelated model day. A lone printed
    day can repair it while preserving its wall time and overnight duration.
    Relative reminders still use immediate_event_range, and ambiguous grids
    are still rejected by the caller.
    """
    text = "\n".join(source_date_texts(raw, cached))
    # An explicitly zoned event can fall on the previous Pacific day. Keep
    # extraction's existing timezone handling instead of moving it a day.
    if _OCR_TIMEZONE_RE.search(text):
        return starts_at, ends_at
    dates = evidence_dates(text)
    if not dates:
        return starts_at, ends_at
    start = datetime.fromisoformat(starts_at).astimezone(PACIFIC_TZ)
    end = datetime.fromisoformat(ends_at).astimezone(PACIFIC_TZ) if ends_at else None
    posted = local_posted_at(raw)

    # Month-name day ranges without a clock cover the entire last day.
    span = re.search(_OCR_DATE_RE.pattern + r"\s*[-–—]\s*(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*((?:19|20)\d{2}))?\b", text, re.IGNORECASE)
    if span and len(dates) == 1 and not _OCR_CLOCK_TIME_RE.search(text):
        month = _MONTHS[span.group(1).lower().rstrip('.')]
        first, last = int(span.group(2)), int(span.group(3))
        year = int(span.group(4)) if span.group(4) else (posted or start).year
        try:
            first_day = datetime(year, month, first, tzinfo=PACIFIC_TZ)
            last_day = datetime(year, month, last, 23, 59, 59, tzinfo=PACIFIC_TZ)
        except ValueError:
            return None
        if first_day > last_day:
            return None
        return first_day.astimezone(timezone.utc).isoformat(), last_day.astimezone(timezone.utc).isoformat()

    if len(dates) != 1:
        # A continuous numeric window also supports days between its endpoints.
        for match in _OCR_NUMERIC_RANGE_RE.finditer(text):
            if (int(match[1]), int(match[2])) <= (start.month, start.day) <= (int(match[3]), int(match[4])):
                return starts_at, ends_at
        return (starts_at, ends_at) if (start.month, start.day) in dates else None

    month, day = next(iter(dates))
    years = set()
    labeled = _labeled_date(text)
    if labeled:
        years.add(labeled[2])
    for form, m, d, span in _scan_printed_dates(text):
        if (m, d) != (month, day):
            continue
        token = text[span[0]:span[1]]
        year_match = re.search(r"(?:^|[/.-])((?:19|20)\d{2})\b", token) if form == _NUMERIC else None
        if form == _NUMERIC and not year_match:
            year_match = re.search(r"[/.-](\d{2})$", token)
        if form in {_MONTH_NAME, _DAY_MONTH}:
            year_match = _OCR_EXPLICIT_YEAR_RE.match(text, span[1])
        if year_match:
            year = int(re.search(r"\d{2,4}", year_match.group()).group())
            years.add(year + 2000 if year < 100 else year)
    if len(years) > 1:
        return None
    year = next(iter(years)) if years else (posted or start).year
    try:
        corrected = start.replace(year=year, month=month, day=day)
        if not years and posted and corrected < posted - timedelta(days=180):
            corrected = corrected.replace(year=year+1)
    except ValueError:
        return None
    printed_range = time_range(text)
    if printed_range:
        (hour, minute), (end_hour, end_minute) = printed_range
        corrected = corrected.replace(hour=hour, minute=minute, second=0, microsecond=0)
        end = corrected.replace(hour=end_hour, minute=end_minute)
        if end <= corrected:
            end += timedelta(days=1)
            if end - corrected > timedelta(hours=12):
                return None
        return corrected.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat()
    # A single clock may be repeated in the flyer and its caption. Do not
    # mistake the sole legible END of an OCR-damaged range for the start.
    clocks = list(_OCR_CLOCK_TIME_RE.finditer(text))
    times = set()
    printed_times = set()
    for match in clocks:
        parts = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)", match.group(), re.IGNORECASE)
        if parts and (clock := _parse_ampm_time(*parts.groups())):
            printed_times.add(clock)
            if not re.search(r"[-–—]\s*$", text[:match.start()]):
                times.add(clock)
    if len(times) == 1 and not end:
        hour, minute = next(iter(times))
        corrected = corrected.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if end and corrected != start:
        end += corrected - start
    # An explicit printed end clock also fixes a model's stale UTC offset
    # across the autumn DST change (02:00 on Nov 1 is standard time).
    if end and local_event_range(raw, cached) is None:
        result = cached.get('result') or {}
        original_start = normalize_timestamptz(result.get('starts_at'))
        original_end = normalize_timestamptz(result.get('ends_at'))
        if original_start and original_end:
            a = datetime.fromisoformat(result['starts_at'].replace('Z', '+00:00'))
            b = datetime.fromisoformat(result['ends_at'].replace('Z', '+00:00'))
            if (b.hour, b.minute) in printed_times:
                end = datetime.combine(corrected.date() + (b.date()-a.date()), b.time(), tzinfo=PACIFIC_TZ)
    if labeled and not clocks and not end and corrected.time() == time(0, 0):
        end = corrected.replace(hour=23, minute=59, second=59)
    return corrected.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat() if end else None


def midnight_end(ocr_text: Any, starts_at: str, ends_at: str | None) -> str | None:
    """Repair a same-day midnight end only when the printed range confirms it.

    This also handles yearful flyers, which the general wall-time override
    deliberately leaves to extraction. Other reversed ranges remain invalid.
    """
    if not isinstance(ocr_text, str) or not ends_at:
        return ends_at
    start = datetime.fromisoformat(starts_at).astimezone(PACIFIC_TZ)
    end = datetime.fromisoformat(ends_at).astimezone(PACIFIC_TZ)
    if (end.date() != start.date() or end.time() != time(0, 0)
            or start.hour < 12 or end > start):
        return ends_at
    if evidence_dates(ocr_text) != {(start.month, start.day)}:
        return ends_at
    for date in _OCR_DATE_RE.finditer(ocr_text):
        year = _OCR_EXPLICIT_YEAR_RE.match(ocr_text, date.end())
        if year and int(re.search(r"\d{4}", year.group()).group()) != start.year:
            return ends_at
    if time_range(ocr_text) != ((start.hour, start.minute), (0, 0)):
        return ends_at
    return (end + timedelta(days=1)).astimezone(timezone.utc).isoformat()


def is_single_session_reminder(
    raw: dict[str, Any], cached: dict[str, Any], starts_at: str, ends_at: str | None,
) -> bool:
    """A story can point to today's session on a reused schedule flyer."""
    posted = local_posted_at(raw)
    if posted is None:
        return False
    start = datetime.fromisoformat(starts_at).astimezone(PACIFIC_TZ)
    if ends_at and datetime.fromisoformat(ends_at).astimezone(PACIFIC_TZ).date() != start.date():
        return False
    texts = list(source_date_texts(raw, cached))
    if not any(
        len(evidence_dates(text)) >= 2
        or len({m.group().lower()[:3] for m in _OCR_WEEKDAY_RE.finditer(text)}) >= 2
        for text in texts
    ):
        # "Today" does not pick one slot from a single-day room/time grid.
        return False
    for text in texts:
        heading = "\n".join(text.splitlines()[:3])
        if re.search(r"\b(?:cancelled|canceled|postponed)\b", heading, re.IGNORECASE):
            continue
        day = _immediate_day(heading)
        if day and start.date() == posted.date() + timedelta(days=day == "tomorrow"):
            return True
    return False


def looks_like_schedule_grid(
    ocr_text: Any,
    starts_at: str,
    ends_at: str | None,
) -> bool:
    if not isinstance(ocr_text, str):
        return False
    if (
        _SCHEDULE_HINT_RE.search(ocr_text)
        and time_range_count(ocr_text) >= _GRID_MIN_TIME_RANGES
    ):
        return True
    dates = evidence_dates(ocr_text)
    clocks = len(list(_OCR_CLOCK_TIME_RE.finditer(ocr_text)))
    if len(dates) >= _GRID_MIN_DISTINCT_DATES:
        headings = sorted(
            (span, (month, day)) for _, month, day, span in _scan_printed_dates(ocr_text)
            if (month, day) in dates
        )
        dates_with_clocks = {
            day for index, (span, day) in enumerate(headings)
            if _OCR_CLOCK_TIME_RE.search(
                ocr_text[span[1]:headings[index + 1][0][0] if index + 1 < len(headings) else len(ocr_text)]
            )
        }
        # Extra "save the date" promotions below one event's clock do not
        # turn that event into a grid. Multiple date/clock groups do.
        if len(dates_with_clocks) >= 2:
            return True
        if ends_at and datetime.fromisoformat(ends_at) - datetime.fromisoformat(starts_at) > timedelta(days=1):
            return True
    weekdays = {m.group().lower()[:3] for m in _OCR_WEEKDAY_RE.finditer(ocr_text)}
    return bool(_SCHEDULE_HINT_RE.search(ocr_text) and len(weekdays) >= 2 and clocks >= 2)


def was_stale_when_posted(
    raw: dict[str, Any],
    starts_at: str,
    ends_at: str | None,
) -> bool:
    posted_at = local_posted_at(raw)
    if posted_at is None:
        return False
    latest_event_time = datetime.fromisoformat(ends_at or starts_at)
    return latest_event_time < posted_at - _STALE_EVENT_GRACE
