"""Content-kind classification with fixed precedence and explicit Python tables.

Only title/description text establishes fundraising or student eligibility.
Audience cohorts are evaluated separately; deadlines match the title only.
Program applications are recognized last, so a dated cutoff still wins, and
they are the one check that also reads a flyer's OCR text.
"""
from __future__ import annotations

import re
from typing import Iterable, Literal


# Shared database/app contract.
CONTENT_KINDS = (
    "student_event",
    "student_deadline",
    "student_application",
    "fundraiser",
    "other",
)
AudienceStance = Literal["student", "restricted", "unspecified"]

_STUDENT_ORIGINS = frozenset({"instagram", "highlander_link", "manual", "submission"})

_FUNDRAISER_TERMS = (
    "fundraiser", "fundraising", "donate", "donation", "proceeds",
    "percentage night", "bake sale", "merch sale", "benefit night", "gofundme",
)

_DEADLINE_TITLE_TERMS = (
    "deadline", "apply by", "register by", "closing date", "last day to",
    "applications due", "application due", "registration closes",
)

# A program you join, not an occasion you attend: multi-week academies,
# fellowships, and cohorts recruit over a long window and have no single start
# time, so they age badly in a chronological feed. Recognized two ways — the
# post says how to apply, or it advertises a program-length commitment — and
# vetoed by an occasion noun in the title, because a Lunch & Learn *about* a
# program is still an event.
_OCCASION_TITLE_PATTERN = re.compile(
    r"""
    \b(?:
        workshop | seminar | webinar | session | sessions
      | office\ hours | drop-?in | hours
      | meeting | fair | expo | panel | mixer | social | reception
      | lunch | luncheon | dinner | breakfast | brunch | bbq | barbecue
      | party | anniversary | celebration | gala | festival | showcase
      | orientation | open\ house | conference | summit | symposium
      | talk | lecture | colloquium | tour | retreat | tabling
      | game | match | concert | screening | performance | watch\ party
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Unambiguous "you apply to join this" language. Bare "application" is
# deliberately absent: "Preparing for Internship Application Season" is a tips
# talk, not an application.
_APPLICATION_CALL_PATTERN = re.compile(
    r"""
    (?:
        applications?\ (?:are\ )?(?:now\ )?open
      | (?:now\ )?accepting\ applications
      | apply\ (?:now|today|here|online|early|by)
      | how\ to\ apply
      | application\ (?:deadline|window|period|portal|form)
      | priority\ deadline
      | enrollment\ is\ limited
      | enroll\ (?:now|today)
      | eligibility\ requirements
      | admission\ requirements
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# The named thing you enroll in.
_PROGRAM_NOUN_PATTERN = re.compile(
    r"""
    \b(?:
        academy|academies
      | fellowship | internship | apprenticeship | residency | practicum
      | bootcamp | boot\ camp | cohort | immersion | intensive | program
    )s?\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# A sign-up window, not an occasion: individually booked appointments.
# Like a program intake it has no single start time, so a chronological feed
# would date it to whichever hour the model guessed. The occasion-noun veto
# still applies, which is what keeps "Office Hours" an event.
_BOOKING_WINDOW_PATTERN = re.compile(
    r"""
    (?:
        book\s+(?:your|a|an)\s+(?:appointment|slot|time|meeting|1:1)
      | (?:select|choose|pick|reserve|claim|grab)\s+(?:a|your)\s+
        (?:time\s+)?(?:slot|appointment)
      | sign\s+up\s+for\s+a\s+(?:slot|time)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_APPOINTMENT_CONTEXT_PATTERN = re.compile(
    r"\b(?:appointments?|1:1|one[- ]on[- ]one|coffee\s+chats?)\b",
    re.IGNORECASE,
)

# "7-week in-person summer program", "10 month fellowship" — a printed span
# next to the program noun. Years are excluded on purpose ("10 Year
# Anniversary" is an event); the span must sit close to the noun so an
# unrelated "6 weeks away" elsewhere in the blurb cannot pair with it.
_PROGRAM_COMMITMENT_PATTERN = re.compile(
    r"""
    \b\d+\s*-?\s*(?:week|month)s?\b
    [\w\s,&'\-]{0,40}?
    \b(?:academy|fellowship|internship|apprenticeship|residency|bootcamp
        |cohort|immersion|intensive|program)s?\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Eligibility grammar is separate from the student-organization vocabulary.
# Generic activity nouns (workshop, concert, wellness) do not qualify.
_STUDENT_ELIGIBILITY = re.compile(
    r"""
    \b(?:
        open\ to\ (?:the\ )?(?:all\ |any\ |current\ |ucr\ )*students
      | (?:all|any|current|ucr|undergraduate|graduate|incoming|new|prospective
        |transfer|international|first-year|first-generation)\ students
      | students?\ (?:are\ |is\ )?(?:welcome|invited|encouraged)
      | for\ (?:ucr\ |all\ |our\ )?students
      | undergraduates?
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_STUDENT_ORG_TERMS = (
    "student organization", "student org", "student club", "student group",
    "student body", "student government", "student leader", "student leaders",
    "student life", "student success center",
    "rso", "asucr", "hackathon", "intramural",
    "general meeting", "general body meeting", "gbm",
    "club meeting", "club fair", "club sport", "club social",
    "greek life", "sorority", "fraternity",
)
_STUDENT_ORG_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in _STUDENT_ORG_TERMS) + r")\b",
    re.IGNORECASE,
)

# Whole audience tokens, including explicit inflections instead of stems.
_STUDENT_AUDIENCE_TOKENS = frozenset({"student", "students"})
_RESTRICTED_AUDIENCE_TOKENS = frozenset({
    "faculty", "staff", "employee", "employees",
    "alumni", "alumna", "alumnae", "alumnus",
    "parent", "parents", "family", "families",
    "retiree", "retirees", "emeritus", "emerita", "emeriti", "emeritae",
    "donor", "donors", "employer", "employers",
})
_OPEN_AUDIENCE_PHRASES = (
    "general public", "everyone", "campus community", "all audiences",
)

# Free food is an independent attribute; preserve the existing caller contract.
_FREE_FOOD_PATTERN = re.compile(
    r"\b(free food|free pizza|pizza provided|free snacks|snacks provided|"
    r"refreshments|lunch provided|dinner provided|boba|free drinks)\b",
    re.IGNORECASE,
)


def detect_free_food(*texts: str | None) -> bool:
    """True when the supplied text blobs advertise free food."""
    return bool(_FREE_FOOD_PATTERN.search(" ".join(text for text in texts if text)))


def _audience_stance(audiences: Iterable) -> AudienceStance:
    """Student cohorts win; public cohorts remove restrictions without promoting."""
    restricted = False
    open_to_all = False
    for audience in audiences or ():
        # Normalize punctuation/spacing so "Parents/Family" and
        # "General Public/Off-Campus Community" match complete words/phrases.
        words = re.findall(r"\w+", str(audience).casefold().replace("_", " "))
        tokens = set(words)
        if tokens & _STUDENT_AUDIENCE_TOKENS:
            return "student"
        name = f" {' '.join(words)} "
        if any(f" {phrase} " in name for phrase in _OPEN_AUDIENCE_PHRASES):
            open_to_all = True
        if tokens & _RESTRICTED_AUDIENCE_TOKENS:
            restricted = True
    return "restricted" if restricted and not open_to_all else "unspecified"


def _is_program_application(title: str, text: str) -> bool:
    """True when the text recruits for a program rather than announcing an event."""
    # An occasion noun in the title settles it: this is something you attend.
    if _OCCASION_TITLE_PATTERN.search(title):
        return False
    if (_BOOKING_WINDOW_PATTERN.search(text)
            and _APPOINTMENT_CONTEXT_PATTERN.search(text)):
        return True
    if _APPLICATION_CALL_PATTERN.search(text):
        return bool(_PROGRAM_NOUN_PATTERN.search(text))
    return bool(_PROGRAM_COMMITMENT_PATTERN.search(text))


def classify_content_kind(
    origin: str,
    *,
    title: str = "",
    description: str = "",
    tags: Iterable = (),
    audiences: Iterable = (),
    ocr_text: str = "",
) -> str:
    """Classify with fundraiser precedence, then eligibility, then title cutoff.

    Tags remain accepted for existing callers but never feed text matching.
    `ocr_text` is read by the program-application check alone: a flyer prints
    the sign-up mechanics ("select a slot", "limited slots") that the caption
    leaves out, but reading it for fundraising or eligibility would promote
    every donation line and audience note in a flyer's fine print.
    """
    title = (title or "").casefold()
    text = f"{title} {description or ''}".casefold()
    if any(term in text for term in _FUNDRAISER_TERMS):
        return "fundraiser"

    # Student/club origins bypass audience and text eligibility checks.
    if origin not in _STUDENT_ORIGINS:
        stance = _audience_stance(audiences)
        if stance == "restricted":
            return "other"
        if (stance == "unspecified"
                and not _STUDENT_ELIGIBILITY.search(text)
                and not _STUDENT_ORG_PATTERN.search(text)):
            return "other"

    # Body text may mention a related cutoff without making this a deadline.
    if any(term in title for term in _DEADLINE_TITLE_TERMS):
        return "student_deadline"

    # Checked after the cutoff so a dated "Applications Due Friday" stays a
    # deadline; this catches the open-ended program pitch behind it.
    if _is_program_application(title, f"{text} {(ocr_text or '').casefold()}"):
        return "student_application"
    return "student_event"
