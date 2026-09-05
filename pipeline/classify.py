"""Centralized content_kind classification for pipeline event rows.

content_kind is the single inclusion contract shared with the app:

  student_event    — attendable, student-relevant (default for club sources)
  student_deadline — student-relevant deadline / application
  fundraiser       — donation / benefit drive (hidden from public browse)
  other            — official / unrelated, not student-relevant (hidden)

Origins:
  instagram, highlander_link, manual, submission
      -> student_event unless a fundraiser/deadline rule overrides.
  localist (events.ucr.edu)
      -> other, promoted to student_event / student_deadline only when
         student-relevance signals are present.

Student relevance means "open to students", not "mentions students". An
official item is promoted only when its audience says students may attend, or
its text says so outright. A curator-set audience restriction (Faculty & Staff,
Alumni) outranks body text, so a staff town hall about student success stays
`other`, and generic activity words ("workshop", "concert") never establish
eligibility on their own.

Precedence (first match wins):
  1. fundraiser terms                       -> fundraiser
  2. cutoff title + student relevance       -> student_deadline
  3. inherently student origin              -> student_event
  4. localist with student relevance        -> student_event
  5. otherwise                              -> other
"""
from __future__ import annotations

import re
from typing import Iterable

CONTENT_KINDS = ("student_event", "student_deadline", "fundraiser", "other")

# Free food is an attribute (does this event hand out food?), not a category.
# Detected deterministically across all sources so a club/social event that
# provides boba still gets flagged without the LLM having to pick it.
_FREE_FOOD_PATTERNS = re.compile(
    r"\b(free food|free pizza|pizza provided|free snacks|snacks provided|"
    r"refreshments|lunch provided|dinner provided|boba|free drinks)\b",
    re.IGNORECASE,
)


def detect_free_food(*texts: str | None) -> bool:
    """True when any of the given text blobs advertises free food."""
    blob = " ".join(t for t in texts if t)
    return bool(_FREE_FOOD_PATTERNS.search(blob))

# Origins that are inherently student/club content.
_STUDENT_ORIGINS = frozenset({"instagram", "highlander_link", "manual", "submission"})

_FUNDRAISER_TERMS = (
    "fundraiser",
    "fundraising",
    "donate",
    "donation",
    "proceeds",
    "percentage night",
    "bake sale",
    "merch sale",
    "benefit night",
    "gofundme",
)

_DEADLINE_TITLE_TERMS = (
    "deadline",
    "apply by",
    "register by",
    "closing date",
    "last day to",
    "applications due",
    "application due",
    "registration closes",
)

# Text that states students may attend, as opposed to merely mentioning them.
# A staff meeting can be *about* students ("hear from faculty, staff, and
# students") without being *open* to them, so eligibility needs explicit
# language or student-organization vocabulary. Deliberately excluded: generic
# activity nouns (workshop, seminar, concert, performance, career, wellness,
# recreation), which describe what happens rather than who may come.
_STUDENT_TEXT_SIGNAL = re.compile(
    r"""
    \b(?:
        open\ to\ (?:the\ )?(?:all\ |any\ |current\ |ucr\ )*students
      | (?:all|any|current|ucr|undergraduate|graduate|incoming|new|prospective
        |transfer|international|first-year|first-generation)\ students
      | students?\ (?:are\ |is\ )?(?:welcome|invited|encouraged)
      | for\ (?:ucr\ |all\ |our\ )?students
      | student\ (?:organization|org|club|group|body|government|leaders?
        |life|success\ center)
      | undergraduates?
      | rso | asucr | hackathon | intramural
      | general\ (?:body\ )?meeting | gbm
      | club\ (?:meeting|fair|sport|social)
      | greek\ life | sorority | fraternity
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Localist `event_audience` filters are curator-set and populated on every
# event, so they outrank body text. Names are matched loosely because the feed
# spells cohorts several ways ("Faculty & Staff", "Parents/Family").
_OPEN_AUDIENCE_TERMS = (
    "general public",
    "public",
    "everyone",
    "campus community",
    "all audiences",
)

_NON_STUDENT_AUDIENCE_TERMS = (
    "faculty",
    "staff",
    "employee",
    "alumni",
    "alumnae",
    "alumnus",
    "parent",
    "famil",
    "retiree",
    "emerit",
    "donor",
    "employer",
)

# _audience_stance results.
_AUDIENCE_STUDENT = "student"
_AUDIENCE_RESTRICTED = "restricted"
_AUDIENCE_UNSPECIFIED = "unspecified"


def _audience_stance(audiences: Iterable) -> str:
    """How an event's audience filters treat students.

    student      -> a student cohort is listed; students may attend.
    restricted   -> only non-student cohorts are listed; students are not the
                    audience, whatever the description talks about.
    unspecified  -> no usable audience data, or an open/public audience that
                    neither targets nor excludes students.
    """
    restricted = False
    open_to_all = False
    for audience in audiences or ():
        name = str(audience).casefold().strip()
        if not name:
            continue
        if "student" in name:
            return _AUDIENCE_STUDENT
        if any(term in name for term in _OPEN_AUDIENCE_TERMS):
            open_to_all = True
        elif any(term in name for term in _NON_STUDENT_AUDIENCE_TERMS):
            restricted = True
    if restricted and not open_to_all:
        return _AUDIENCE_RESTRICTED
    return _AUDIENCE_UNSPECIFIED


def _haystack(
    title: str,
    description: str,
    tags: Iterable,
    audiences: Iterable,
) -> str:
    parts = [title or "", description or ""]
    parts.extend(str(t) for t in (tags or []))
    parts.extend(str(a) for a in (audiences or []))
    return " ".join(parts).casefold()


def _has_student_signal(origin: str, text: str, audiences: Iterable) -> bool:
    if origin in _STUDENT_ORIGINS:
        return True

    stance = _audience_stance(audiences)
    if stance == _AUDIENCE_STUDENT:
        return True
    if stance == _AUDIENCE_RESTRICTED:
        # An explicit non-student audience settles it; body text mentioning
        # students describes the subject, not who is invited.
        return False

    return bool(_STUDENT_TEXT_SIGNAL.search(text))


def classify_content_kind(
    origin: str,
    *,
    title: str = "",
    description: str = "",
    tags: Iterable = (),
    audiences: Iterable = (),
) -> str:
    text = _haystack(title, description, tags, audiences)

    if any(term in text for term in _FUNDRAISER_TERMS):
        return "fundraiser"

    student = _has_student_signal(origin, text, audiences)

    # A deadline label means the listed timestamp is a cutoff. Descriptions may
    # mention related deadlines, scholarships, or grants without changing what
    # the scheduled item itself represents, so only strong title language can
    # opt an item into deadline presentation.
    if student and any(
        term in (title or "").casefold() for term in _DEADLINE_TITLE_TERMS
    ):
        return "student_deadline"

    if origin in _STUDENT_ORIGINS:
        return "student_event"

    # Official / Localist default: only surface when student-relevant.
    return "student_event" if student else "other"
