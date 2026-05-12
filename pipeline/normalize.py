"""Roll raw/<handle>/*.json into a single deduped output/stories.json.

Decoupling scrape and normalize lets the frontend re-read a stable file
without racing the scraper, and gives us a clean place to drop in
extraction (OCR / vision LLM → structured CampusEvents) later.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from config import OUTPUT_FILE, RAW_DIR, ensure_dirs, load_accounts

log = logging.getLogger("pipeline.normalize")


def _load_account_meta() -> dict[str, dict[str, Any]]:
    return {a["handle"]: a for a in load_accounts()}


def collect() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not RAW_DIR.exists():
        return items
    for handle_dir in sorted(RAW_DIR.iterdir()):
        if not handle_dir.is_dir():
            continue
        for path in handle_dir.glob("*.json"):
            try:
                with path.open() as f:
                    items.append(json.load(f))
            except json.JSONDecodeError:
                log.warning("skipping malformed file: %s", path)
    return items


def dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for it in items:
        by_id[it["id"]] = it  # last write wins (raw files are immutable by id anyway)
    return list(by_id.values())


def enrich(items: list[dict[str, Any]], meta: dict[str, dict[str, Any]]) -> None:
    for it in items:
        m = meta.get(it["handle"], {})
        it["account_label"] = m.get("label")
        it["account_category"] = m.get("category")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ensure_dirs()
    items = dedupe(collect())
    enrich(items, _load_account_meta())
    items.sort(key=lambda it: it["posted_at"], reverse=True)

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "stories": items,
    }
    with OUTPUT_FILE.open("w") as f:
        json.dump(output, f, indent=2)
    log.info("Wrote %d stories to %s", len(items), OUTPUT_FILE)


if __name__ == "__main__":
    main()
