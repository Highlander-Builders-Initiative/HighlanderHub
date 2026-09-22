"""Date and time evidence parsing for event flyers and captions."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterator
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

_OCR_DATE_RE = re.compile(
    r"\b("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?|tember)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?"
    r")(?:\.\s*|\s+)(\d{1,2})(?:st|nd|rd|th)?\b",
    re.IGNORECASE,
)

_OCR_DAY_MONTH_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + "|".join(_MONTHS) + r")\b",
    re.IGNORECASE,
)

_OCR_NUMERIC_DATE_RE = re.compile(
    r"(?<![\w/.$])(?:\d{4}-)?(\d{1,2})([/.-])(\d{1,2})"
    r"(?:\2(\d{4}|\d{2}))?(?![\w/])"
)

_OCR_NUMERIC_RANGE_RE = re.compile(
    r"(?<![\w/.$])(\d{1,2})/(\d{1,2})\s*(?:[-\u2013\u2014]|to|thru|through)\s*"
    r"(\d{1,2})/(\d{1,2})(?![\w/])",
    re.IGNORECASE,
)

_OCR_WEEKDAY_RE = re.compile(
    r"\b(?:mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:rs(?:day)?)?|"
    r"fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b",
    re.IGNORECASE,
)

_OCR_CLOCK_TIME_RE = re.compile(
    r"\b\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?|\b\d{1,2}:\d{2}\b|\bnoon\b|\bmidnight\b",
    re.IGNORECASE,
)

_OCR_EXPLICIT_YEAR_RE = re.compile(r"\s*,?\s*(?:19|20)\d{2}\b")

_OCR_TIME_RANGE_RE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)"
    r"(?:\s*(?:[-–—]|to)\s*|\s+)"
    r"(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)\b",
    re.IGNORECASE,
)

_OCR_COMPACT_TIME_RANGE_RE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(?:[-–—]|to)\s*"
    r"(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)\b",
    re.IGNORECASE,
)

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
    """When the post was posted, in Pacific wall time."""
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


def _bare_date_is_corroborated(text: str, span: tuple[int, int]) -> bool:
    """Whether a bare "5/28" here reads as a date rather than a fraction.

    A temporal preposition, a clock time on the flyer, a second
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
    # Captions often give only an all-day date: "doing it again on 9/25".
    # Require slash notation here so "on 5.62" cannot turn a decimal into a day.
    if "/" in text[start:end] and re.search(
        r"\b(?:on|until|through|thru|by)\s*$", text[max(0, start-20):start], re.IGNORECASE
    ):
        return True
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


def weekday_range_dates(text: str, *, year: int) -> dict[tuple[int, int], set[int]]:
    """Days in short, consistent weekday/date ranges and their explicit years.

    The candidate year only checks weekday labels when no year was printed.
    Keep printed years attached to every day so callers cannot accept a range
    from another year just because its month and day match.
    """
    endpoint = (r"(" + _OCR_WEEKDAY_RE.pattern + r"),?\s+" + _OCR_DATE_RE.pattern
                + r"(?:\s*,?\s*((?:19|20)\d{2})\b)?")
    days: dict[tuple[int, int], set[int]] = {}
    for match in re.finditer(endpoint + r"\s*(?:[-–—]|to|through|thru)\s*" + endpoint, text, re.I):
        first_weekday, first_month, first_number, first_year, last_weekday, last_month, last_number, last_year = match.groups()
        try:
            first = date(int(first_year or last_year or year), _MONTHS[first_month.lower()], int(first_number))
            last = date(int(last_year or first_year or year), _MONTHS[last_month.lower()], int(last_number))
        except ValueError:
            continue
        weekdays = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
        if (not 0 <= (last - first).days <= 6
                or weekdays[first.weekday()] != first_weekday[:3].lower()
                or weekdays[last.weekday()] != last_weekday[:3].lower()):
            continue
        for offset in range((last - first).days + 1):
            day = first + timedelta(days=offset)
            years = days.setdefault((day.month, day.day), set())
            if first_year or last_year:
                years.add(day.year)
    return days


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
