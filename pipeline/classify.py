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

Precedence (first match wins):
  1. fundraiser terms                       -> fundraiser
  2. deadline terms + student relevance     -> student_deadline
  3. inherently student origin              -> student_event
  4. localist with student relevance        -> student_event
  5. otherwise                              -> other
"""
from __future__ import annotations

from typing import Iterable

CONTENT_KINDS = ("student_event", "student_deadline", "fundraiser", "other")

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

_DEADLINE_TERMS = (
    "deadline",
    "apply now",
    "apply by",
    "applications due",
    "application due",
    "applications open",
    "registration closes",
    "register by",
    "nomination",
    "nominations",
    "scholarship",
    "grant",
    "fellowship",
    "last day to",
)

_STUDENT_SIGNAL_TERMS = (
    "undergraduate",
    "graduate student",
    "students",
    "student",
    "club",
    "organization",
    "rso",
    "career",
    "internship",
    "workshop",
    "info session",
    "info-session",
    "information session",
    "free food",
    "wellness",
    "src",
    "recreation",
    "intramural",
    "athletics",
    "performance",
    "recital",
    "concert",
    "hackathon",
    "gbm",
    "general meeting",
)

# Localist event_audience filter names that mark student relevance.
_STUDENT_AUDIENCES = frozenset(
    name.casefold()
    for name in (
        "Students",
        "Undergraduate Students",
        "Graduate Students",
        "Current Students",
        "Prospective Students",
        "Student Organizations",
    )
)


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
    if any(str(a).casefold() in _STUDENT_AUDIENCES for a in (audiences or [])):
        return True
    return any(term in text for term in _STUDENT_SIGNAL_TERMS)


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

    if student and any(term in text for term in _DEADLINE_TERMS):
        return "student_deadline"

    if origin in _STUDENT_ORIGINS:
        return "student_event"

    # Official / Localist default: only surface when student-relevant.
    return "student_event" if student else "other"
