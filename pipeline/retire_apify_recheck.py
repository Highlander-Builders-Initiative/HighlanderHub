"""Archive an inaccessible paid recheck run after an explicit Apify account switch.

This does not recover its output or cancel the old actor. A later normal run
may buy replacement checks using the new account.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def retire(directory: Path, run_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9]+", run_id):
        raise ValueError("Provide the exact Apify run ID from the Forbidden error")
    pending = directory / "post_recheck_run-details.json"
    archived = directory / f"post_recheck_run-details.retired-{run_id}.json"
    if not pending.exists() and archived.is_file():
        return archived  # Safe to repeat a recovery-only workflow.
    saved = json.loads(pending.read_text())
    if saved.get("id") != run_id or saved.get("consumed"):
        raise ValueError("Saved pending recheck does not match the requested run ID")
    if archived.exists():
        raise ValueError("Retired run backup already exists; inspect it before proceeding")
    pending.rename(archived)
    return archived


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--directory", type=Path, default=Path(__file__).parent / "data")
    args = parser.parse_args()
    archived = retire(args.directory, args.run_id)
    print(f"Retained old recheck intent at {archived}; no API calls made. "
          "The next normal run may purchase replacement checks.")


if __name__ == "__main__":
    main()
