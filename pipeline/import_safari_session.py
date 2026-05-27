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


def main(argv: list[str] | None = None) -> None:
    username = _parse_username(argv)
    L = instaloader.Instaloader()

    print("Extracting Instagram cookies from Safari...")
    try:
        cookies = browser_cookie3.safari(domain_name="instagram.com")
        L.context._session.cookies.update(cookies)
        print("Cookies successfully extracted!")
    except Exception as e:
        print(f"Error loading cookies from Safari: {e}")
        print(
            "Make sure you granted Full Disk Access to Terminal and are "
            "logged into Instagram in Safari."
        )
        sys.exit(1)

    L.context.username = username

    session_file = Path.home() / ".config" / "instaloader" / f"session-{username}"
    session_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        L.save_session_to_file(str(session_file))
        print(f"\n🎉 SUCCESS! Session file successfully created at:")
        print(f"   {session_file}\n")
        print("🔒 Encode for IG_SESSION_FILE (GitHub Actions secret) with:")
        print(f"   base64 -i ~/.config/instaloader/session-{username}")
    except Exception as e:
        print(f"Error saving session file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
