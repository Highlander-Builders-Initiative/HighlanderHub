"""One stop decision shared by both Instagram collection channels.

Stories (`scrape.py`) and feed posts (`scrape_posts.py`) collect through the
same logged-in account from the same machine, so a challenge or throttle seen by
either applies to both. `classify` is the only place that decides what counts as
one. The channel that meets one records a pause here, and each collector checks
it before its first request — including the other channel later in the same
run. Asking again right after Instagram has pushed back is what escalates a
throttle into a checkpoint.

Only collection pauses. Extraction, assessment, and publication work from what
is already on disk and never use the Instagram session.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Iterator

from instaloader.exceptions import (
    AbortDownloadException,
    InstaloaderException,
    LoginRequiredException,
    QueryReturnedBadRequestException,
    QueryReturnedForbiddenException,
    TooManyRequestsException,
)

from config import INSTAGRAM_COOLDOWN_FILE, INSTAGRAM_COOLDOWN_HOURS
from post_archive import iso, parse_instant, read_json, utc_now, write_json

log = logging.getLogger("pipeline.instagram_cooldown")


class Kind(StrEnum):
    THROTTLED = "throttled"
    CHALLENGED = "challenged"
    # A pause record that exists but can't be read. Nobody can tell what it was,
    # so nothing lifts it except an operator deleting the file.
    UNREADABLE = "unreadable"


# Instaloader retries a failed query and re-raises the last error as a plain
# ConnectionException, and reports most refusals as a 400 or a `fail` status,
# so for those the message is the only signal left.
_CHALLENGE_MARKERS = (
    "challenge_required",
    "checkpoint_required",
    "feedback_required",
    "login_required",
)
_THROTTLE_MARKERS = ("too many requests", "please wait a few minutes")


@dataclass(frozen=True)
class Block:
    """Instagram refusing the account, not one bad account or a dropped connection."""

    kind: Kind
    reason: str


@dataclass(frozen=True)
class Pause:
    kind: Kind
    reason: str
    detail: str
    # None only for UNREADABLE, whose channel and end nobody knows.
    channel: str | None
    until: datetime | None

    def describe(self) -> str:
        if self.kind is Kind.UNREADABLE:
            return (
                f"the pause record could not be read ({self.detail}); both "
                "Instagram channels stay paused until it is removed"
            )
        when = self.until.astimezone().strftime("%Y-%m-%d %H:%M %Z")
        return (
            f"{self.channel} collection was {self.kind} ({self.reason}); both "
            f"Instagram channels are paused until {when}"
        )


class EveryAccountRejected(RuntimeError):
    """A story batch refused for every account, each asked about on its own."""


class CollectionPaused(RuntimeError):
    """A collector refused to start because Instagram pushed back recently."""


class CollectionStopped(RuntimeError):
    """Instagram challenged or throttled a collector mid-run; both channels are paused."""


# A pause that could not be written. It still stops the other channel in this
# process; only later runs miss it.
_UNSAVED: Pause | None = None


def _instaloader_errors(exc: BaseException | None) -> Iterator[BaseException]:
    """`exc` and the Instaloader errors it wraps, stopping at anything else.

    Walking past our own exceptions would re-read the 429 a CollectionStopped
    was raised from, and pause again for a decision already made.
    """
    seen: set[int] = set()
    while isinstance(exc, (InstaloaderException, AbortDownloadException)) and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        exc = exc.__cause__ or exc.__context__


def classify(exc: BaseException, *, lone_400: bool = False) -> Block | None:
    """Whether `exc` is Instagram pushing back on the account.

    A bare 400 is ambiguous in a story batch — it can be one bad userid, which
    the split-retry isolates — but a request about a single account
    (`lone_400`) has nothing to isolate, so there it means the session.
    """
    if isinstance(exc, EveryAccountRejected):
        return Block(Kind.CHALLENGED, "every account rejected")
    errors = list(_instaloader_errors(exc))
    for err in errors:
        if isinstance(err, TooManyRequestsException):
            return Block(Kind.THROTTLED, "rate limited")
        if isinstance(err, AbortDownloadException):
            # Instaloader's own "stop producing requests": a checkpoint,
            # challenge or feedback_required reply, or a session sent to login.
            return Block(Kind.CHALLENGED, "challenge or logged-out session")
        if isinstance(err, LoginRequiredException):
            return Block(Kind.CHALLENGED, "login required")
        if isinstance(err, QueryReturnedForbiddenException):
            return Block(Kind.CHALLENGED, "forbidden (challenge or blocked session)")
    text = " ".join(str(err) for err in errors).lower()
    if any(marker in text for marker in _CHALLENGE_MARKERS):
        return Block(Kind.CHALLENGED, "challenge")
    if any(marker in text for marker in _THROTTLE_MARKERS):
        return Block(Kind.THROTTLED, "rate limited")
    if lone_400 and any(isinstance(err, QueryReturnedBadRequestException) for err in errors):
        return Block(Kind.CHALLENGED, "bad request (stale session or challenge)")
    return None


def pause(block: Block, channel: str, detail: str, *, now: datetime | None = None) -> Pause:
    """Pause collection on both channels for the cooldown, starting now."""
    global _UNSAVED
    record = Pause(
        kind=block.kind,
        reason=block.reason,
        detail=detail[:300],
        channel=channel,
        until=(now or utc_now()) + timedelta(hours=INSTAGRAM_COOLDOWN_HOURS),
    )
    try:
        write_json(
            INSTAGRAM_COOLDOWN_FILE,
            {
                "kind": record.kind,
                "reason": record.reason,
                "detail": record.detail,
                "channel": record.channel,
                "until": iso(record.until),
            },
        )
    except OSError as exc:
        _UNSAVED = record
        log.error(
            "Could not save the Instagram pause to %s (%s); it holds for this run only.",
            INSTAGRAM_COOLDOWN_FILE,
            exc,
        )
    else:
        _UNSAVED = None
    log.error("%s: %s", record.describe(), record.detail)
    return record


def stop(block: Block, channel: str, exc: BaseException) -> CollectionStopped:
    """Pause both channels and build the error that ends `channel`'s run."""
    paused = pause(block, channel, str(exc))
    return CollectionStopped(f"{paused.describe()}. {exc}")


def _load(saved: Any) -> Pause:
    kind = Kind(saved["kind"])
    until = parse_instant(saved["until"])
    if kind is Kind.UNREADABLE or until is None:
        raise ValueError(f"not a recorded pause: {saved!r}")
    return Pause(
        kind=kind,
        reason=saved["reason"],
        detail=saved["detail"],
        channel=saved["channel"],
        until=until,
    )


def current(*, now: datetime | None = None) -> Pause | None:
    """The pause in force, if any. A record that can't be read counts as one."""
    record = _UNSAVED
    if record is None:
        try:
            record = _load(read_json(INSTAGRAM_COOLDOWN_FILE))
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return Pause(
                kind=Kind.UNREADABLE,
                reason="unreadable pause record",
                detail=str(exc),
                channel=None,
                until=None,
            )
    if record.until is not None and (now or utc_now()) >= record.until:
        return None
    return record


def ensure_collection_allowed(channel: str, *, now: datetime | None = None) -> None:
    """Refuse to start `channel` while a pause from either channel is in force."""
    active = current(now=now)
    if active is None:
        return
    resume = {
        Kind.THROTTLED: (
            "a new session does not lift a rate limit; delete "
            f"{INSTAGRAM_COOLDOWN_FILE} to resume sooner"
        ),
        Kind.CHALLENGED: (
            "refresh the session with import_safari_session.py, or delete "
            f"{INSTAGRAM_COOLDOWN_FILE}, to resume sooner"
        ),
        Kind.UNREADABLE: f"check {INSTAGRAM_COOLDOWN_FILE}, then delete it to resume",
    }[active.kind]
    raise CollectionPaused(
        f"Not collecting Instagram {channel}: {active.describe()}. Content already "
        f"on disk is still processed; {resume}."
    )


def lift_challenge() -> Pause | None:
    """Clear a challenge pause once a fresh session is saved.

    Nothing else lifts: a new cookie for the same account does not reset a rate
    limit, and nobody knows what an unreadable record was. Returns the pause
    still in force, if any.
    """
    global _UNSAVED
    active = current()
    if active is None or active.kind is not Kind.CHALLENGED:
        return active
    _UNSAVED = None
    INSTAGRAM_COOLDOWN_FILE.unlink(missing_ok=True)
    log.info("Lifted the Instagram challenge pause (%s)", active.reason)
    return None
