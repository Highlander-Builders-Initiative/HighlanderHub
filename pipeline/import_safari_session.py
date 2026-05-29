"""Import Instagram session cookies from Safari into an Instaloader session file.

Usage:
    python import_safari_session.py YOUR_IG_USERNAME
    python import_safari_session.py --username YOUR_IG_USERNAME
    IG_USERNAME=YOUR_IG_USERNAME python import_safari_session.py

Log into Instagram in Safari first. Terminal may need Full Disk Access to read
Safari cookies. Run from the pipeline venv (see pipeline/README.md).
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

# pyrefly: ignore [missing-import]
import browser_cookie3
# pyrefly: ignore [missing-import]
import instaloader

from config import IG_USERNAME


def _parse_username(argv: list[str] | None = None) -> str:
    parser = argparse.ArgumentParser(
        description="Save Instaloader session cookies imported from Safari."
    )
    parser.add_argument(
        "username",
        nargs="?",
        default=IG_USERNAME,
        help="Instagram login name (default: IG_USERNAME env var)",
    )
    args = parser.parse_args(argv)
    username = (args.username or "").strip()
    if not username:
        parser.error(
            "Instagram username required. Pass it as an argument or set IG_USERNAME "
            "(e.g. in pipeline/.env)."
        )
    return username


def _mask(value: str) -> str:
    """Mask a credential so it can be printed for verification without leaking it."""
    return f"{value[:6]}…{value[-4:]} (len {len(value)})" if len(value) > 12 else "(too short)"


def _existing_sessionid(session_file: Path) -> str | None:
    """Read the sessionid already saved (if any) so we can tell whether this
    import actually captured a *new* login. The session file is a pickled
    name->value cookie dict (see instaloader's save_session)."""
    if not session_file.exists():
        return None
    try:
        with session_file.open("rb") as fh:
            data = pickle.load(fh)
    except Exception:
        return None
    return data.get("sessionid") if isinstance(data, dict) else None


def main(argv: list[str] | None = None) -> None:
    username = _parse_username(argv)
    session_file = Path.home() / ".config" / "instaloader" / f"session-{username}"

    # browser_cookie3 reads Safari's *on-disk* cookie file, and Safari flushes
    # cookies to disk lazily. If Safari is still open you can silently re-import
    # a stale (or just-logged-out, now-invalid) session. Quitting forces the flush.
    print(
        "→ Before running this: log into Instagram in Safari, then FULLY QUIT "
        "Safari (⌘Q).\n  Otherwise your new login may not be flushed to disk and "
        "you'll re-import a stale session.\n"
    )

    previous_sessionid = _existing_sessionid(session_file)

    L = instaloader.Instaloader()
    print("Extracting Instagram cookies from Safari...")
    try:
        cookies = browser_cookie3.safari(domain_name="instagram.com")
        L.context._session.cookies.update(cookies)
    except Exception as e:
        print(f"Error loading cookies from Safari: {e}")
        print(
            "Make sure you granted Full Disk Access to Terminal and are "
            "logged into Instagram in Safari."
        )
        sys.exit(1)

    # Validate that we actually captured a logged-in session. The old code would
    # happily overwrite a working session file with a logged-out/empty cookie jar
    # and still print "SUCCESS".
    sessionid = L.context._session.cookies.get("sessionid")
    if not sessionid:
        print(
            "\n❌ No `sessionid` cookie found for instagram.com in Safari.\n"
            "   You're either not logged in, or Safari hasn't flushed cookies to disk.\n"
            "   Log into Instagram in Safari, fully quit Safari (⌘Q), then retry.\n"
            "   Refusing to overwrite the existing session file with a logged-out one."
        )
        sys.exit(1)

    print(f"Cookies extracted. sessionid = {_mask(sessionid)}")
    if previous_sessionid is not None and sessionid == previous_sessionid:
        print(
            "\n⚠️  This sessionid is IDENTICAL to the one already saved — this import\n"
            "   did NOT capture a new login. Safari almost certainly hadn't flushed\n"
            "   your fresh session to disk. Fully quit Safari (⌘Q) and run this again."
        )

    L.context.username = username
    session_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        L.save_session_to_file(str(session_file))
    except Exception as e:
        print(f"Error saving session file: {e}")
        sys.exit(1)

    print(f"\n🎉 SUCCESS! Session file written to:")
    print(f"   {session_file}\n")
    print("🔒 Encode for IG_SESSION_FILE (GitHub Actions secret) with:")
    print(f"   base64 -i ~/.config/instaloader/session-{username}")


if __name__ == "__main__":
    main()
