"""Recognize stories that reshare someone else's feed post.

Clubs frequently promote an event by resharing the original post to their
story rather than posting their own flyer. Because we only crawl stories,
those reshares are a real acquisition channel — but N clubs resharing one
post yields N stories, and the event identity in `extract_stories` is keyed
on the crawled account, so the same event lands N times.

Instagram renders a reshare as an embed card whose header is the original
post's byline. That byline names the original author, which is the identity
the event should actually be keyed on. This module recovers it from OCR text.

The byline is also the first text Vision returns, so an LLM handed the raw
OCR will happily title the event `bluejadeandjoel and ucr_dance`. Callers use
`strip_byline` to keep account chrome out of user-visible fields.
"""
from __future__ import annotations

import re
from typing import Iterable, NamedTuple

# Instagram handles: letters, digits, underscore, dot; 2-30 chars. Kept
# lowercase on purpose — a byline is always rendered lowercase, while flyer
# body text that happens to read like a handle ("SWE", "Bytes") is not.
_HANDLE = r"[a-z0-9_][a-z0-9._]{2,29}"

# "a and b", "a, b and c" — the co-author byline of a collab post.
_MULTI_BYLINE = re.compile(rf"^{_HANDLE}(?:, ?{_HANDLE})*(?: and {_HANDLE})+$")
# A lone handle, e.g. a plain reshare of a single-author post.
_SINGLE_BYLINE = re.compile(rf"^{_HANDLE}$")

_SPLIT_HANDLES = re.compile(r",| and ")

# How far into the OCR text a byline may appear. Vision sometimes emits a
# fragment of the story background before the embed card.
_BYLINE_SEARCH_LINES = 10
# A caption line ("<handle> Joel Mejia Smith: it's been a while...") needs
# real text after the handle to count as attribution rather than coincidence.
_MIN_CAPTION_CHARS = 9
_MIN_SINGLE_HANDLE_LEN = 4


class Byline(NamedTuple):
    """A confirmed reshare byline and the accounts it names."""

    line: str
    handles: tuple[str, ...]

    @property
    def origin(self) -> str:
        return self.handles[0]


def _unwrapped_lines(ocr_text: str | None) -> list[str]:
    """Return non-empty OCR lines with wrapped bylines rejoined.

    A long co-author list wraps mid-byline, so Vision emits
    "a, b, c and" / "d" as two lines.
    """
    text = ocr_text if isinstance(ocr_text, str) else ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    joined: list[str] = []
    index = 0
    while index < len(lines):
        current = lines[index]
        while current.endswith(" and") and index + 1 < len(lines):
            index += 1
            current = f"{current} {lines[index]}"
        joined.append(current)
        index += 1
    return joined


def _handles_in(byline: str) -> list[str]:
    return [part.strip() for part in _SPLIT_HANDLES.split(byline) if part.strip()]


def _has_letter(text: str) -> bool:
    return any(character.isalpha() for character in text)


def find_byline(
    ocr_text: str | None,
    viewer_handle: str = "",
    known_handles: Iterable[str] = (),
) -> Byline | None:
    """Return the reshare byline in this story's OCR text, or None.

    `viewer_handle` is the account whose story we crawled; `known_handles` is
    the crawl roster. Both only widen the set of handles trusted to anchor a
    byline — an ordinary flyer line like "pizza and snacks." is handle-shaped
    but names nobody we follow, so it is rejected.
    """
    lines = _unwrapped_lines(ocr_text)
    trusted = set(known_handles) | ({viewer_handle} if viewer_handle else set())

    # A co-author byline is distinctive enough on its own, provided at least
    # one name is an account we actually know about.
    for line in lines[:_BYLINE_SEARCH_LINES]:
        if not _MULTI_BYLINE.match(line):
            continue
        handles = _handles_in(line)
        if not all(_has_letter(handle) for handle in handles):
            continue
        if not any(handle in trusted for handle in handles):
            continue
        return Byline(line, tuple(handles))

    # A lone handle is only a byline if the card's caption is attributed to
    # it. Match case-sensitively: the byline and the caption prefix are the
    # same rendered handle, whereas a flyer's "swe" / "SWE at UCR" is not.
    for position, line in enumerate(lines[:_BYLINE_SEARCH_LINES]):
        if not _SINGLE_BYLINE.match(line):
            continue
        if not _has_letter(line) or len(line) < _MIN_SINGLE_HANDLE_LEN:
            continue
        for other, caption in enumerate(lines):
            if other == position:
                continue
            if caption.startswith(f"{line} ") and len(caption) - len(line) >= _MIN_CAPTION_CHARS:
                return Byline(line, (line,))
    return None


def reshared_origin_handle(
    ocr_text: str | None,
    viewer_handle: str = "",
    known_handles: Iterable[str] = (),
) -> str | None:
    """Return the handle that authored the reshared post, or None."""
    byline = find_byline(ocr_text, viewer_handle, known_handles)
    return byline.origin if byline else None


def strip_byline(
    title: str,
    ocr_text: str | None,
    viewer_handle: str = "",
    known_handles: Iterable[str] = (),
) -> str:
    """Drop reshare chrome the LLM may have lifted into a user-visible title.

    Only a byline this module actually confirmed is stripped, and only on an
    exact-case match, so a flyer whose own wording opens with the same letters
    ("SWE X NSBE STUDY JAM") is left alone. Returns "" when the title was
    nothing but chrome, which tells the caller there is no real title to show.
    """
    cleaned = (title if isinstance(title, str) else "").strip()
    byline = find_byline(ocr_text, viewer_handle, known_handles)
    if not cleaned or byline is None:
        return cleaned

    # Longest first, so "a, b and c" wins over the bare "a" inside it.
    chrome = sorted({byline.line, *byline.handles}, key=len, reverse=True)
    for candidate in chrome:
        if cleaned == candidate:
            return ""
        if cleaned.startswith(f"{candidate} "):
            cleaned = cleaned[len(candidate):].strip(" -–—:|")
            break
    return "" if cleaned in chrome else cleaned
