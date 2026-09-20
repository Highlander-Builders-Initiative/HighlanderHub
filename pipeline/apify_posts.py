"""Collect date-filtered Instagram posts with a pinned, verified Apify build.

Already-paid legacy datasets remain readable; new runs filter before billing.
Checkpoints require explicit profile completion, durable writes and no cap.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit

import requests
from hpix_contract import hpix_item, completed_profiles as hpix_completed_profiles

from config import DATA_DIR, POST_BACKFILL_SINCE, load_accounts
from post_archive import (_mirrored_media_ids as known_post_ids,
                          hydrate_local_posts, iso, media_key,
                          parse_instant, read_json, write_json, write_post)

log = logging.getLogger("pipeline.apify_posts")
ACTOR_ID = "nH2AHrwxeTRJoN5hX"  # apify/instagram-post-scraper
ACTOR_BUILD = "0.0.599"
HPIX_ACTOR_ID = "JER1eC8E7teQWMN3p"  # hpix/instagram-scraper
HPIX_BUILD = "1.2.17"
LEGACY_ACTOR_ID = "Y5mzw9TLFReI0d6gQ"
API = "https://api.apify.com/v2"
RUN_FILE = DATA_DIR / "apify_run.json"
TERMINAL = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
PAGE_SIZE = 1000
PLAN_FILE = DATA_DIR / "apify_plan.json"
RUNS_DIR = DATA_DIR / "apify_runs"
DISCOVERY_OVERLAP_SECONDS = 300
INCOMPLETE_RETRY_HOURS = 8
BATCH_SIZE = 25


class PartialCollection(RuntimeError):
    """Saved records may be extracted despite incomplete account coverage."""


class CollectionHalted(PartialCollection):
    """Do not start another paid batch until the cause has been reviewed."""


def hpix_input(**values) -> dict:
    return {"profiles": [], "posts": [], "scrape_posts": True,
            "scrape_reels": True, "scrape_profile_data": False,
            "scrape_detailed_data": False, "scrape_restricted_posts": False,
            "include_raw_data": True, **values}


class ApifyClient:
    def __init__(self, token: str, run_file: Path | None = None):
        if not token.strip():
            raise ValueError("APIFY_TOKEN is required")
        self.run_file = run_file or RUN_FILE
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {token.strip()}"

    def request(self, method: str, path: str, **kwargs):
        # Never retry a run-creation POST: an ambiguous response may already
        # have started a billed run. Tokens stay in headers, never URLs/logs.
        response = self.session.request(method, f"{API}/{path}", timeout=60, **kwargs)
        response.raise_for_status()
        return response.json()

    def run(self, actor_input: dict, *, max_charge: float, timeout: int) -> dict:
        # Keep the internal discovery request stable so cached official/legacy
        # runs resume without a second purchase. Only new starts use hpix.
        metadata = {"usernames": actor_input["username"],
                    "newer_than": actor_input["onlyPostsNewerThan"],
                    "posts_per_profile": actor_input["resultsLimit"],
                    "actor_id": HPIX_ACTOR_ID, "build": HPIX_BUILD, "consumed": False}
        payload = hpix_input(profiles=actor_input["username"],
                             posts_per_account=actor_input["resultsLimit"],
                             fromDate=actor_input["onlyPostsNewerThan"])
        cutoff = parse_instant(actor_input["onlyPostsNewerThan"])
        if cutoff is None:
            raise ValueError("Invalid hpix discovery cutoff")
        # hpix's fromDate schema accepts only whole dates. Its server-side
        # shouldSkip receives the native post node (not the output envelope).
        # Continue walking past old pins; only fromDate ends the feed walk.
        payload["fromDate"] = cutoff.date().isoformat()
        payload["custom_functions"] = (
            "{ shouldSkip: (item) => { const raw = item.data ?? item; "
            "const t = raw.taken_at_timestamp ?? raw.taken_at; "
            "return typeof t === 'number' && t < " + str(cutoff.timestamp()) +
            "; }, shouldContinue: () => true }")
        # Fixed reservation survives crashes and prevents details spending
        # above the existing batch/cycle ceiling. Unused reserves are not spent.
        return self._run(payload, metadata, max_charge=max_charge * .8, timeout=timeout)

    def _run(self, actor_input: dict, metadata: dict, *, max_charge: float, timeout: int) -> dict:
        digest = hashlib.sha256(json.dumps(actor_input, sort_keys=True).encode()).hexdigest()
        saved = read_json(self.run_file) if self.run_file.exists() else {}
        if saved and not saved.get("consumed"):
            # Reuse even when the rolling date boundary changed since failure.
            if saved.get("usernames") != metadata["usernames"]:
                raise RuntimeError("Unconsumed Apify run has a different roster; resolve data/apify_run.json first")
            if not saved.get("id"):
                raise RuntimeError("Apify start outcome unknown; inspect Console and resolve the saved run intent before retrying")
            run = self.request("GET", f"actor-runs/{saved['id']}")["data"]
        else:
            write_json(self.run_file, {**metadata, "starting": True})
            run = self.request("POST", f"acts/{metadata['actor_id']}/runs", json=actor_input,
                               params={"build": metadata['build'], "timeout": timeout,
                                       "memory": 1024, "maxTotalChargeUsd": max_charge})["data"]
            write_json(self.run_file, {**metadata, "id": run["id"], "input_hash": digest,
                                      "started_at": run["startedAt"]})
        log.info("Apify run: https://console.apify.com/actors/runs/%s", run["id"])
        deadline = time.monotonic() + timeout + 120
        while run["status"] not in TERMINAL:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Apify run {run['id']} still active; next invocation will resume it")
            time.sleep(10)
            run = self.request("GET", f"actor-runs/{run['id']}")["data"]
        return run

    def completed_profiles(self, run_id: str) -> set[str]:
        """Pinned build's explicit cutoff acknowledgement, including empty feeds.

        SUCCEEDED and a short dataset alone do not prove per-profile coverage.
        If the log contract changes, fail closed without advancing checkpoints.
        """
        return completed_profiles_from_log(self.run_log(run_id))

    def run_log(self, run_id: str) -> str:
        response = self.session.get(f"{API}/logs/{run_id}", timeout=60)
        response.raise_for_status()
        return response.text

    def details(self, codes: list[str], *, max_charge: float, timeout: int) -> tuple[dict, list]:
        path = self.run_file.with_name(self.run_file.stem + "-details.json")
        saved = read_json(path) if path.exists() else {}
        # A replay may have fewer unknown IDs after a partial archive write.
        # Resume the original paid request, never replace it with a smaller one.
        codes = saved.get("usernames", sorted(codes))
        client = ApifyClient(self.session.headers["Authorization"].removeprefix("Bearer "), path)
        run = client._run(hpix_input(posts=[f"https://www.instagram.com/p/{code}/" for code in codes]),
                          {"usernames": codes, "actor_id": HPIX_ACTOR_ID,
                           "build": HPIX_BUILD, "consumed": False, "purpose": "details"},
                          max_charge=max_charge, timeout=timeout)
        if run.get("actId") != HPIX_ACTOR_ID:
            raise CollectionHalted("Unexpected actor in saved detail run")
        return run, list(client.items(run["defaultDatasetId"]))

    def items(self, dataset: str):
        offset = 0
        while True:
            page = self.request("GET", f"datasets/{dataset}/items",
                                params={"format": "json", "offset": offset, "limit": PAGE_SIZE})
            if not isinstance(page, list):
                raise RuntimeError("Apify dataset is not a JSON array")
            yield from page
            if len(page) < PAGE_SIZE:
                break
            offset += len(page)


def _handle(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.]{0,29}", value):
        raise ValueError("invalid Instagram handle")
    return value.lower()


def profile_handle(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc not in {"instagram.com", "www.instagram.com"}:
        raise ValueError("invalid input profile URL")
    return _handle(parsed.path.strip("/"))


# Verified against build 0.0.599: coverage ends in exactly one of three ways --
# the cutoff is reached, the feed runs out, or nothing public sits in the window.
COMPLETION_SIGNALS = (
    re.compile(r"INFO\s+No more posts within the wanted time range, finishing "
               r"https://www\.instagram\.com/([A-Za-z0-9_.]+)(?=\s|$)"),
    re.compile(r"INFO\s+NO RESULTS: zero public posts for "
               r"https://www\.instagram\.com/([A-Za-z0-9_.]+) within the given requirements"),
    re.compile(r"INFO\s+\[END-OF-RESULTS\]: ([A-Za-z0-9_.]+) confirmed end of results at pos \d+"),
)


def completed_profiles_from_log(text: str) -> set[str]:
    """Only an explicit per-profile acknowledgement may advance a checkpoint.

    An unrecognised log contract therefore fails closed rather than treating a
    short dataset as proof that the profile was scanned to its cutoff.
    """
    handles = set()
    for pattern in COMPLETION_SIGNALS:
        for match in pattern.findall(text):
            try:
                handles.add(_handle(match))
            except ValueError:
                continue
    return handles


def official_item(item: dict) -> dict:
    """Map verified detailedData output to our native ingestion contract."""
    handle = profile_handle(item.get("inputUrl", ""))
    timestamp = parse_instant(item.get("timestamp"))
    kinds = {"Image": 1, "Video": 2, "Sidecar": 8}
    def media(node):
        return {"media_type": kinds.get(node.get("type")), "image_url": node.get("displayUrl")}
    return {**media(item), "id": item.get("id"), "pk": item.get("id"),
            "code": item.get("shortCode"), "scraped_username": handle,
            "taken_at": timestamp.timestamp() if timestamp else None,
            "user": {"username": item.get("ownerUsername"), "pk": item.get("ownerId")},
            "coauthor_producers": item.get("coauthorProducers") or [],
            "caption": {"text": item.get("caption")},
            "carousel_media": [media(node) for node in (item.get("childPosts") or [])]}


def identity(item: dict, accounts: dict, seen_at: datetime) -> tuple[str, str, datetime]:
    """Validate routing/date before inspecting irrelevant historical media.

    The legacy actor rounded numeric pk values in JavaScript. Its composite
    string id retains the exact Instagram media ID and must take precedence.
    """
    handle = _handle(item.get("scraped_username"))
    if handle not in accounts:
        raise ValueError(f"unrequested profile: {handle}")
    value = item.get("id")
    if isinstance(value, str) and re.fullmatch(r"[0-9]+(?:_[0-9]+)?", value):
        media_id = value.split("_")[0]
    else:
        value = item.get("pk")
        if isinstance(value, bool) or isinstance(value, float) or (
                isinstance(value, int) and value > 2**53 - 1):
            raise ValueError(f"{handle}: unsafe numeric media identity")
        media_id = str(value or "")
    if not re.fullmatch(r"[0-9]+", media_id):
        raise ValueError(f"{handle}: invalid media identity")
    taken_at = item.get("taken_at")
    if isinstance(taken_at, bool) or not isinstance(taken_at, (int, float)) or taken_at <= 0:
        raise ValueError(f"{handle}: invalid taken_at")
    posted_at = datetime.fromtimestamp(taken_at, timezone.utc)
    if posted_at > seen_at + timedelta(minutes=5):
        raise ValueError(f"{handle}: future taken_at")
    return handle, media_id, posted_at


def owner_userid(owner: dict) -> Any:
    """Keep one numeric owner identity: this actor reports IDs as strings."""
    value = owner.get("pk") or owner.get("id")
    return int(value) if isinstance(value, str) and value.isdigit() else value


def normalize(item: dict, accounts: dict, seen_at: datetime) -> dict:
    """Map the actor's native Instagram output into the existing post archive."""
    handle, media_id, posted_at = identity(item, accounts, seen_at)
    owner = item.get("user") or {}
    owner_name = _handle(owner.get("username"))
    authors = [owner, *(item.get("coauthor_producers") or [])]
    expected_id = accounts[handle].get("instagram_user_id")
    if not any(_handle(author.get("username")) == handle and
               (not expected_id or str(author.get("pk") or author.get("id")) == str(expected_id))
               for author in authors):
        raise ValueError(f"{handle}: owner/accepted coauthor does not match roster")
    shortcode = item.get("code")
    if not media_id.isascii() or not media_id.isdigit() or not isinstance(shortcode, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", shortcode):
        raise ValueError(f"{handle}: invalid media identity")
    kind = item.get("media_type")
    if kind not in (1, 2, 8):
        raise ValueError(f"{handle}: unsupported media_type")
    nodes = item.get("carousel_media") if kind == 8 else [item]
    if not isinstance(nodes, list) or not nodes:
        raise ValueError(f"{handle}: missing carousel media")
    media = []
    for index, node in enumerate(nodes):
        candidates = (node.get("image_versions2") or {}).get("candidates") or []
        candidates = [entry for entry in candidates if isinstance(entry.get("url"), str)
                      and entry["url"].startswith("https://")]
        # Actual sones 1.5.10 datasets use flattened image_url fields, including
        # each carousel child, rather than the shape in the actor's README.
        if not candidates and isinstance(node.get("image_url"), str) and node["image_url"].startswith("https://"):
            candidates = [{"url": node["image_url"]}]
        if not candidates:
            raise ValueError(f"{handle}: missing image/cover at slide {index}")
        best = max(candidates, key=lambda entry: (entry.get("width") or 0) * (entry.get("height") or 0))
        url = best["url"]
        media.append({"index": index, "is_video": node.get("media_type") == 2,
                      "image_url": url, "media_key": media_key(url) or f"{media_id}_{index}"})
    caption = item.get("caption")
    text = caption.get("text") if isinstance(caption, dict) else None
    if caption is not None and (not isinstance(caption, dict) or (text is not None and not isinstance(text, str))):
        raise ValueError(f"{handle}: invalid caption")
    return {"media_id": media_id, "handle": handle, "owner_username": owner_name,
            "owner_userid": owner_userid(owner), "shortcode": shortcode,
            "permalink": f"https://www.instagram.com/p/{shortcode}/",
            "posted_at": iso(posted_at), "typename": {1: "GraphImage", 2: "GraphVideo", 8: "GraphSidecar"}[kind],
            "caption": text, "caption_mentions": re.findall(r"@([\w.]+)", text or ""),
            "media": media, "has_video": any(m["is_video"] for m in media),
            "fetched_at": iso(seen_at)}


def checkpoints(handles: list[str], now: datetime) -> dict:
    """Read durable state strictly: a cache miss must never reset activation."""
    from db import client
    result = {}
    for offset in range(0, len(handles), 200):
        rows = client().rpc("claim_post_activation", {"entries": [
            {"handle": handle, "activated_at": iso(now)} for handle in handles[offset:offset + 200]]}).execute().data
        if not isinstance(rows, dict):
            raise RuntimeError("Cannot confirm durable post activation")
        result.update(rows)
    if any(not parse_instant((result.get(handle) or {}).get("activated_at")) for handle in handles):
        raise RuntimeError("Missing durable post activation")
    return result


def boundary(checkpoint: dict, overlap_seconds: int = DISCOVERY_OVERLAP_SECONDS) -> datetime:
    activation = parse_instant(checkpoint["activated_at"])
    through = parse_instant(checkpoint.get("scanned_through"))
    return max(activation, through - timedelta(seconds=overlap_seconds)) if through else activation


def mirror(records: list[dict]) -> None:
    from db import upsert_batched
    columns = ("media_id", "handle", "owner_username", "shortcode", "permalink",
               "posted_at", "typename", "caption", "has_video", "media", "fetched_at")
    upsert_batched("instagram_posts", [{**{key: record.get(key) for key in columns}, "record": record}
                                      for record in records], on_conflict="media_id")


def charge_limit_reason(run: dict, max_charge: float, exported: int) -> str | None:
    """A charge-limited success is not evidence of complete profile coverage."""
    events = ((run.get("pricingInfo") or {}).get("pricingPerEvent") or {}).get("actorChargeEvents") or {}
    if run.get("actId") == HPIX_ACTOR_ID:
        try:
            counts = run["chargedEventCounts"]
            if counts.get("restricted_post_scraped", 0):
                return "Unexpected restricted-post charge; collection halted"
            prices = {key: float(events[key]["eventPriceUsd"]) for key in
                      ("post_scraped", "profile_scraped", "individual_post_scraped", "apify-actor-start")}
            total = sum(float(count) * float(events[key]["eventPriceUsd"]) for key, count in counts.items())
            # Billing counters can lag dataset output. Use at least the observed
            # row count at the cheapest enabled row price before trusting coverage.
            total = max(total, exported * min(prices["post_scraped"], prices["individual_post_scraped"])
                        + prices["apify-actor-start"])
            ceiling = (run.get("options") or {}).get("maxTotalChargeUsd") or max_charge
            if total + max(prices.values()) > float(ceiling) + 1e-9:
                return "Actor reached its charge ceiling; retaining collection checkpoints"
            return None
        except (KeyError, TypeError, ValueError):
            return "Cannot verify actor charge-limit coverage from run pricing metadata"
    if run.get("actId") == ACTOR_ID:
        try:
            post_price = float(events["post"]["eventPriceUsd"])
            detail_price = float(events["post-details"]["eventPriceUsd"])
            charged = run["chargedEventCounts"]
            total = charged.get("post", 0) * post_price + charged.get("post-details", 0) * detail_price
            ceiling = (run.get("options") or {}).get("maxTotalChargeUsd") or max_charge
            if total + post_price + detail_price > float(ceiling) + 1e-9:
                return "Actor reached its charge ceiling; retaining collection checkpoints"
            return None
        except (KeyError, TypeError, ValueError):
            return "Cannot verify actor charge-limit coverage from run pricing metadata"
    try:
        post_price = float(events["apify-default-dataset-item"]["eventPriceUsd"])
        start_price = float(events["apify-actor-start"]["eventPriceUsd"])
    except (KeyError, TypeError, ValueError):
        return "Cannot verify actor charge-limit coverage from run pricing metadata"
    charged = run.get("chargedEventCounts") or {}
    starts = max(1, charged.get("apify-actor-start", 1))
    posts = max(exported, charged.get("apify-default-dataset-item", 0))
    ceiling = (run.get("options") or {}).get("maxTotalChargeUsd", max_charge)
    if ceiling is None:
        ceiling = max_charge
    if start_price * starts + post_price * (posts + 1) > float(ceiling) + 1e-9:
        return "Actor reached its charge ceiling; retaining collection checkpoints"
    return None


def prepare_hpix(api, run, rows, accounts, boundaries, known, now, *, max_charge, timeout):
    """Resolve unknown cross-owner posts once, before the normal archive loop.

    Error placeholders retain the originating profile, so one failure cannot
    become quiet coverage or unnecessarily invalidate unrelated profiles.
    """
    mapped, needed = [], {}
    for row in rows:
        handle = row.get("input") if isinstance(row, dict) else None
        try:
            if row.get("error") or (row.get("kind") == "profile" and row.get("data") is None):
                # Media fetch failures can identify the profile by a feed URL.
                # Keep these attributable failures out of schema-failure counts.
                if isinstance(handle, str) and "://" in handle:
                    parsed = urlsplit(handle)
                    handle = profile_handle(parsed._replace(path=parsed.path.strip("/").split("/")[0]).geturl())
                mapped.append({"scraped_username": handle, "_profile_failure": True,
                               "_collection_error": row.get("error") or "profile retrieval failed"})
                continue
            if row.get("kind") not in {"post", "reel"}:
                raise ValueError("profile retrieval failed or unexpected row kind")
            item = hpix_item(row)
            handle, media_id, posted = identity(item, accounts, now)
            if posted >= boundaries[handle] and media_id not in known:
                code = item.get("code")
                if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", code):
                    raise ValueError("invalid shortcode")
                owner = item["user"]
                expected = accounts[handle].get("instagram_user_id")
                if (_handle(owner.get("username")) != handle or
                        (expected and str(owner.get("pk")) != str(expected))):
                    needed.setdefault(code, []).append(item)
            mapped.append(item)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError) as exc:
            mapped.append({"scraped_username": handle, "_collection_error": str(exc)})
    detail_info = {}
    detail_error = None
    replacements = {}
    if needed:
        saved = read_json(api.run_file)
        requested = parse_instant(saved.get("newer_than"))
        old_rows = any(isinstance(item.get("taken_at"), (int, float)) and requested and
                       item["taken_at"] < requested.timestamp() for item in mapped)
        blocked = (timeout < 60 or old_rows or run.get("status") != "SUCCEEDED" or
                   charge_limit_reason(run, max_charge, len(rows)))
        if not blocked:
            # Both caps were reserved before either paid request; never rely on
            # immediately reported usage to decide what remains to spend.
            detail_run, detail_rows = api.details(sorted(needed), max_charge=max_charge * .2, timeout=timeout)
            detail_info = {"detail_run_id": detail_run["id"],
                           "detail_usage_usd": detail_run.get("usageTotalUsd")}
            detail_error = charge_limit_reason(detail_run, max_charge * .2, len(detail_rows))
            if detail_error and "restricted-post" in detail_error:
                detail_info["halt_reason"] = detail_error
            if detail_run["status"] != "SUCCEEDED":
                detail_error = f"Detail run {detail_run['id']} ended {detail_run['status']}"
            if detail_run["status"] == "ABORTED":
                detail_info["halt_reason"] = detail_error
            if not detail_error:
                for row in detail_rows:
                    node = row.get("data")
                    code = node.get("code") if isinstance(node, dict) else None
                    if code in needed and row.get("kind") in {"post", "reel"} and not row.get("error"):
                        replacements[code] = node
        else:
            detail_error = "Feed run incomplete or charge-limited; no detail run started"
        for code, items in needed.items():
            for item in items:
                try:
                    detail = replacements.get(code)
                    if detail is None:
                        raise ValueError(detail_error or "missing collaboration detail")
                    routed = {**detail, "scraped_username": item["scraped_username"]}
                    if identity(routed, accounts, now) != identity(item, accounts, now):
                        raise ValueError("detail identity/timestamp differs from feed")
                    # A feed can include a repost with no accepted collaboration.
                    # Validate it fully under its actual owner, then skip it;
                    # a requested-name/wrong-ID mismatch still fails closed.
                    authors = [routed.get("user") or {}, *(routed.get("coauthor_producers") or [])]
                    names = {_handle(author.get("username")) for author in authors}
                    unrelated = routed["scraped_username"] not in names
                    if unrelated:
                        owner = _handle(routed["user"]["username"])
                        normalize({**routed, "scraped_username": owner}, {owner: {}}, now)
                    else:
                        normalize(routed, accounts, now)
                    item.clear()
                    item.update(routed)
                    if unrelated:
                        item["_unrelated"] = True
                except (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError) as exc:
                    item["_collection_error"] = str(exc)
                    item["_profile_failure"] = True
    return mapped, detail_info


def collect(api: ApifyClient, accounts: dict, state: dict, now: datetime,
            *, limit: int, max_charge: float, timeout: int,
            cutoff: str | None = None,
            account_boundaries: dict | None = None) -> None:
    from db import upsert_batched
    deadline = time.monotonic() + timeout
    boundaries = {handle: boundary(entry) for handle, entry in state.items()}
    if account_boundaries is not None:
        boundaries = {h: parse_instant(v) for h, v in account_boundaries.items()}
    if POST_BACKFILL_SINCE:
        backfill = parse_instant(POST_BACKFILL_SINCE)
        if backfill is None:
            raise ValueError("Invalid PIPELINE_POST_BACKFILL_SINCE")
        boundaries = dict.fromkeys(accounts, backfill)
    oldest = min(boundaries.values())
    # Read strictly from durable storage before spending on a run. Losing the
    # local cache must not turn previously saved posts into editable new input.
    known = known_post_ids()
    requested_cutoff = cutoff or iso(oldest - timedelta(seconds=1))
    # The schema accepts UTC Z, not an explicit +00:00 suffix. Measured against
    # build 0.0.599: the cutoff alone still exports (and charges for) pinned
    # posts of any age, while skipPinnedPosts with it drops only the pins older
    # than the window and keeps the ones inside it.
    actor_cutoff = iso(parse_instant(requested_cutoff)).replace("+00:00", "Z")
    run = api.run({"username": sorted(accounts), "resultsLimit": limit,
                   "onlyPostsNewerThan": actor_cutoff, "skipPinnedPosts": True,
                   "dataDetailLevel": "detailedData"}, max_charge=max_charge, timeout=timeout)
    observed_at = max(now, datetime.now(timezone.utc))
    saved = read_json(api.run_file)
    actor_id = run.get("actId", saved.get("actor_id", LEGACY_ACTOR_ID))
    if actor_id not in {ACTOR_ID, LEGACY_ACTOR_ID, HPIX_ACTOR_ID}:
        raise CollectionHalted(f"Unsupported saved actor {actor_id}; no new paid batches started")
    official = actor_id == ACTOR_ID
    hpix = actor_id == HPIX_ACTOR_ID
    limit = saved["posts_per_profile"]
    scan_start = parse_instant(saved["started_at"])
    if scan_start is None:
        raise RuntimeError("Apify run missing startedAt")
    counts = {handle: set() for handle in accounts}
    bad = set()
    seen = set()
    errors = []
    dataset = run.get("defaultDatasetId")
    if not dataset:
        raise RuntimeError("Apify run has no dataset")
    # Needed before the loop: a profile with nothing inside the window reports
    # an error item, and only the log separates that from a private or blocked
    # one. Treating the empty case as a failure would strand its checkpoint.
    completed = api.completed_profiles(run["id"]) if official else set()
    pending = []
    exported = 0
    ignored_old = 0
    validated = 0
    invalid = 0
    outside_actor_cutoff = 0
    detail_info = {}
    source = api.items(dataset)
    if hpix:
        completed = hpix_completed_profiles(api.run_log(run["id"]))
        rows = list(source)
        # Profile error rows have no data, and override any apparent completion.
        source, detail_info = prepare_hpix(api, run, rows, accounts, boundaries, known,
                                          observed_at, max_charge=max_charge,
                                          timeout=max(1, int(deadline - time.monotonic())))

    def flush() -> None:
        if pending:
            mirror(pending)
            for record in pending:
                write_post(record)
            pending.clear()

    try:
        for item in source:
            exported += 1
            original = item
            try:
                if hpix and item.get("_profile_failure"):
                    handle = _handle(item.get("scraped_username"))
                    if handle not in accounts:
                        raise ValueError(f"unrequested profile: {handle}")
                    bad.add(handle)
                    errors.append(f"{handle}: {item['_collection_error']}")
                    continue
                if hpix and item.get("_collection_error"):
                    raise ValueError(item["_collection_error"])
                if official:
                    if item.get("error"):
                        handle = profile_handle(item.get("inputUrl", ""))
                        if handle not in accounts:
                            raise ValueError(f"unrequested profile: {handle}")
                        # Only the verified empty-window diagnostic is benign.
                        # A completion line must never mask a lookup/block error.
                        if item["error"] != "no_items" or handle not in completed:
                            bad.add(handle)
                            errors.append(f"{handle}: actor error {item['error']}")
                        continue
                    item = official_item(item)
                handle, media_id, posted_at = identity(item, accounts, observed_at)
                counts[handle].add(media_id)
                if (official or hpix) and posted_at < parse_instant(saved.get("newer_than") or actor_cutoff):
                    outside_actor_cutoff += 1
                if posted_at < boundaries[handle]:
                    ignored_old += 1
                    continue
                if hpix and item.get("_unrelated"):
                    # Details verified this rejection. Explicit profile completion
                    # still proves coverage when every result is an unrelated repost.
                    validated += 1
                    continue
                if media_id in known or media_id in seen:
                    validated += 1
                    continue
                record = normalize(item, accounts, observed_at)
                validated += 1
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError) as exc:
                invalid += 1
                handle = item.get("scraped_username") if isinstance(item, dict) else None
                if official and handle is None and isinstance(original, dict):
                    try:
                        handle = profile_handle(original.get("inputUrl", ""))
                    except (ValueError, TypeError, AttributeError):
                        pass
                if isinstance(handle, str) and handle.lower() in accounts:
                    bad.add(handle.lower())
                else:
                    bad.update(accounts)
                errors.append(str(exc))
                continue
            handle, media_id = record["handle"], record["media_id"]
            counts[handle].add(media_id)
            if parse_instant(record["posted_at"]) < boundaries[handle]:
                continue
            # A saved post is a snapshot. Never refresh captions/media or
            # trigger changed-input OCR when a boundary page repeats its ID.
            if media_id in known or media_id in seen:
                continue
            # Remote first: local extraction may only see durably accepted records.
            pending.append(record)
            seen.add(media_id)
            if len(pending) >= 100:
                flush()
    finally:
        # Persist a completed prefix even if the next dataset page fails.
        flush()
    saved_cutoff = parse_instant(saved.get("newer_than"))
    successful = run["status"] == "SUCCEEDED"
    if outside_actor_cutoff:
        successful = False
        errors.append(f"Actor exported {outside_actor_cutoff} posts older than its requested cutoff")
    if saved_cutoff is not None and saved_cutoff > oldest:
        successful = False
        errors.append("Resumed run did not cover the newly requested older cutoff; rerun for coverage")
    limited = charge_limit_reason(run, max_charge, exported)
    if limited:
        successful = False
        errors.append(limited)
    updates = []
    for handle, entry in state.items():
        coverage = handle in completed if official or hpix else bool(counts[handle])
        complete = successful and handle not in bad and coverage and len(counts[handle]) < limit
        if not complete:
            errors.append(f"{handle}: incomplete ({len(counts[handle])} posts, limit {limit}, run {run['status']})")
        updates.append({"handle": handle, "activated_at": entry["activated_at"],
                        "scanned_through": iso(scan_start) if complete else entry.get("scanned_through"),
                        "last_scan_at": iso(now), "last_status": "ok" if complete else "incomplete"})
    if updates:
        upsert_batched("instagram_post_checkpoints", updates, on_conflict="handle")
    halt_reason = detail_info.get("halt_reason")
    if run["status"] == "ABORTED":
        halt_reason = f"Apify run {run['id']} was aborted; remaining paid batches stopped"
    elif invalid and not validated:
        halt_reason = f"Apify output contract failed for all {invalid} relevant result(s); remaining paid batches stopped"
    elif outside_actor_cutoff:
        halt_reason = "Actor violated the paid date filter; remaining paid batches stopped"
    elif limited and "restricted-post" in limited:
        halt_reason = limited
    write_json(api.run_file, {**saved, "consumed": True, "status": run["status"],
                          "saved_posts": len(seen), "errors": errors,
                          "exported": exported, "ignored_old": ignored_old,
                          "invalid": invalid, "halt_reason": halt_reason,
                          **{k: v for k, v in detail_info.items() if k != "halt_reason"},
                          "usage_usd": run.get("usageTotalUsd"), "build_id": run.get("buildId"),
                          "dataset_id": dataset})
    log.info("Apify: archived %d posts; %d incomplete results", len(seen), len(errors))
    if halt_reason:
        raise CollectionHalted(halt_reason)
    if errors:
        raise PartialCollection("; ".join(errors[:10]) + f" ({len(errors)} issues; see {api.run_file})")


def _group_jobs(cutoffs: dict[str, datetime]) -> list[dict]:
    """Group only nearby cutoffs: a stale account cannot widen other hours."""
    groups: dict[datetime, dict[str, datetime]] = {}
    for handle, cutoff in sorted(cutoffs.items()):
        bucket = cutoff.replace(minute=0, second=0, microsecond=0)
        groups.setdefault(bucket, {})[handle] = cutoff
    chunks = [dict(list(entries.items())[offset:offset + BATCH_SIZE])
              for _, entries in sorted(groups.items(), reverse=True)
              for offset in range(0, len(entries), BATCH_SIZE)]
    return [{"mode": "discovery", "handles": sorted(entries),
             "cutoff": iso(min(entries.values()) - timedelta(seconds=1)),
             "boundaries": {h: iso(value) for h, value in entries.items()},
             "done": False}
            for entries in chunks]


def _allocate(jobs: list[dict], cents: int) -> None:
    # Reserve at least one cent per start, then weight the rest by roster size.
    # Round in integer cents so the sum of actor ceilings cannot exceed budget.
    if not jobs:
        return
    if cents < len(jobs):
        raise ValueError("Apify budget is too small for the number of checkpoint groups")
    available = cents - len(jobs)
    weight = sum(len(job["handles"]) for job in jobs)
    shares = [1 + available * len(job["handles"]) // weight for job in jobs]
    for index in range(cents - sum(shares)):
        shares[index % len(shares)] += 1
    for job, share in zip(jobs, shares):
        job["max_charge"] = share / 100


def plan_jobs(accounts: dict, state: dict, now: datetime,
              *, limit: int, max_charge: float, overlap_seconds: int = DISCOVERY_OVERLAP_SECONDS,
              retry_hours: int = INCOMPLETE_RETRY_HOURS) -> list[dict]:
    recent = now - timedelta(hours=retry_hours)
    # Retrying incomplete discovery is distinct from rechecking saved posts:
    # this profile may still have unseen posts beyond the failed scan boundary.
    eligible = {handle: entry for handle, entry in state.items()
                if handle in accounts and (entry.get("last_status") != "incomplete"
                or (parse_instant(entry.get("last_scan_at")) or datetime.min.replace(tzinfo=timezone.utc)) <= recent)}
    cutoffs = {handle: boundary(entry, overlap_seconds) for handle, entry in eligible.items()}
    if POST_BACKFILL_SINCE:
        backfill = parse_instant(POST_BACKFILL_SINCE)
        if backfill is None:
            raise ValueError("Invalid PIPELINE_POST_BACKFILL_SINCE")
        cutoffs = dict.fromkeys(eligible, backfill)
    jobs = _group_jobs(cutoffs)
    _allocate(jobs, int(Decimal(str(max_charge)) * 100))
    cycle = uuid.uuid4().hex
    for index, job in enumerate(jobs):
        job.update({"file": str(RUNS_DIR / f"{cycle}-{index}.json"), "limit": limit})
    return jobs


def execute_plan(token: str, accounts: dict, state: dict, now: datetime,
                 plan: dict, timeout: int) -> None:
    if plan.get("halt_reason"):
        raise CollectionHalted(plan["halt_reason"])
    deadline = time.monotonic() + timeout
    errors = []
    for job in plan["jobs"]:
        # Old Actions caches may contain pending refresh work. Cancel it before
        # inspecting a run file or making any API call, even if it was started.
        if job.get("mode") == "refresh":
            job.update({"done": True, "errors": [], "skipped": "post rechecks disabled"})
            write_json(PLAN_FILE, plan)
            continue
        if job.get("mode") != "discovery":
            raise RuntimeError("Unsupported saved Apify job mode")
        job.pop("refresh", None)
        if job["done"]:
            errors.extend(job.get("errors") or [])
            continue
        if not set(job["handles"]).issubset(accounts):
            raise RuntimeError("Pending Apify plan contains removed accounts; review apify_plan.json")
        path = Path(job["file"])
        saved = read_json(path) if path.exists() else {}
        if not saved.get("consumed"):
            remaining = int(deadline - time.monotonic())
            if remaining < 60:
                raise PartialCollection("Collection time budget exhausted; unfinished batches will resume")
            api = ApifyClient(token, path)
            try:
                collect(api, {h: accounts[h] for h in job["handles"]},
                        {h: state[h] for h in job["handles"]}, now,
                        limit=job["limit"], max_charge=job["max_charge"], timeout=remaining,
                        cutoff=job["cutoff"],
                        account_boundaries=job.get("boundaries"))
            except CollectionHalted as exc:
                saved = read_json(path)
                job["done"] = bool(saved.get("consumed"))
                job["errors"] = saved.get("errors") or [str(exc)]
                plan["halt_reason"] = str(exc)
                write_json(PLAN_FILE, plan)
                raise
            except PartialCollection:
                # A terminal partial dataset is consumed; do not launch the same
                # paid batch again when a different batch needs recovery.
                pass
            saved = read_json(path)
        job["done"] = bool(saved.get("consumed"))
        job["errors"] = saved.get("errors") or []
        errors.extend(job["errors"])
        if saved.get("halt_reason"):
            plan["halt_reason"] = saved["halt_reason"]
            write_json(PLAN_FILE, plan)
            raise CollectionHalted(plan["halt_reason"])
        write_json(PLAN_FILE, plan)
    plan["complete"] = all(job["done"] for job in plan["jobs"])
    write_json(PLAN_FILE, plan)
    if errors:
        raise PartialCollection("; ".join(errors[:10]) + "; see data/apify_plan.json")


def main(*, resume_halted: bool = False) -> None:
    plan = read_json(PLAN_FILE) if PLAN_FILE.exists() else {}
    if plan.get("halt_reason"):
        if not resume_halted:
            raise CollectionHalted(plan["halt_reason"] + "; after fixing the cause, run apify_posts.py --resume-halted")
        plan.pop("halt_reason")
        write_json(PLAN_FILE, plan)
    token = os.environ.get("APIFY_TOKEN", "")
    if not token.strip():
        raise ValueError("APIFY_TOKEN is required")
    limit = int(os.environ.get("APIFY_POSTS_PER_PROFILE") or "100")
    charge = float(os.environ.get("APIFY_MAX_CHARGE_USD") or "10")
    timeout = int(os.environ.get("APIFY_TIMEOUT_SECONDS") or "1800")
    overlap = int(os.environ.get("APIFY_DISCOVERY_OVERLAP_SECONDS") or "300")
    retry_hours = int(os.environ.get("APIFY_INCOMPLETE_RETRY_HOURS") or "8")
    if (not 1 <= limit <= 500 or not 0.01 <= charge <= 1000 or not 60 <= timeout <= 3600
            or not 0 <= overlap <= 3600 or retry_hours < 8):
        raise ValueError("Invalid Apify collection limits")
    accounts = {_handle(a["handle"]): a for a in load_accounts()}
    if not 1 <= len(accounts) <= 4000:
        raise ValueError("Apify requires 1..4000 configured profiles")
    now = datetime.now(timezone.utc)
    state = checkpoints(sorted(accounts), now)
    hydrate_local_posts()
    if not plan or plan.get("complete"):
        legacy = read_json(RUN_FILE) if RUN_FILE.exists() else {}
        if legacy and not legacy.get("consumed"):
            # Finish the already-paid pre-batching run once before switching.
            jobs = [{"mode": "discovery", "handles": legacy["usernames"],
                     "cutoff": legacy["newer_than"], "done": False,
                     "file": str(RUN_FILE), "limit": legacy["posts_per_profile"], "max_charge": charge}]
        else:
            jobs = plan_jobs(accounts, state, now, limit=limit, max_charge=charge,
                             overlap_seconds=overlap, retry_hours=retry_hours)
        plan = {"created_at": iso(now), "complete": False, "max_charge": charge, "jobs": jobs}
        write_json(PLAN_FILE, plan)
    log.info("Apify plan: %d batches, %.2f USD total reserved ceiling", len(plan["jobs"]),
             sum(job["max_charge"] for job in plan["jobs"]))
    execute_plan(token, accounts, state, now, plan, timeout)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume-halted", action="store_true", help="Explicitly resume remaining batches after reviewing an abort or output contract failure")
    logging.basicConfig(level=logging.INFO)
    main(resume_halted=parser.parse_args().resume_halted)
