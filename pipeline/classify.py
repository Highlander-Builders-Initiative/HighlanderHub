"""Content-kind classification with fixed precedence and explicit Python tables.

Only title/description text establishes fundraising or student eligibility.
Audience cohorts are evaluated separately; deadlines match the title only.
"""
from __future__ import annotations

import re
from typing import Iterable, Literal


# Shared database/app contract.
CONTENT_KINDS = ("student_event", "student_deadline", "fundraiser", "other")
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


def classify_content_kind(
    origin: str,
    *,
    title: str = "",
    description: str = "",
    tags: Iterable = (),
    audiences: Iterable = (),
) -> str:
    """Classify with fundraiser precedence, then eligibility, then title cutoff.

    Tags remain accepted for existing callers but never feed text matching.
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
    return "student_event"
