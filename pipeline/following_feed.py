"""Chronological Following discovery using a browser-observed GraphQL query.

No query IDs or authentication tokens are stored here. Bootstrap the real web
client, capture its Following request, then replay from the first page through
that browser context. Never infer Following mode from the URL alone.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator
from urllib.parse import parse_qs, urlparse

from instaloader.exceptions import (
    AbortDownloadException, LoginRequiredException, TooManyRequestsException,
)

from config import FOLLOWING_CHECKPOINT_FILE, POST_OVERLAP_DAYS
from post_archive import iso, media_key, parse_instant, read_json, write_json

log = logging.getLogger("pipeline.following_feed")
CONNECTION = "xdt_api__v1__feed__timeline__connection"
URL = "https://www.instagram.com/?variant=following"
MAX_PAGES = 100


def is_graphql_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname == "www.instagram.com" and parsed.path.rstrip("/") in (
        "/graphql/query", "/api/graphql",
    )


def request_template(url: str, body: str | None) -> dict[str, str] | None:
    """Accept only observed web GraphQL requests explicitly selecting Following."""
    if not is_graphql_url(url):
        return None
    try:
        form = {key: values[0] for key, values in parse_qs(body or "").items()}
        variables = json.loads(form.get("variables", "{}"))
        if (form.get("doc_id") and isinstance(variables, dict)
                and isinstance(variables.get("data"), dict)
                and variables["data"].get("pagination_source") == "following"
                and "after" in variables):
            return form
    except (ValueError, TypeError):
        pass
    return None


def page_form(template: dict[str, str], cursor: str | None) -> dict[str, str]:
    form = dict(template)
    variables = json.loads(form["variables"])
    variables["after"] = cursor
    variables["before"] = None
    variables["last"] = None
    # Captured view telemetry describes the bootstrap page, not replayed pages.
    variables["data"]["feed_view_info"] = ""
    form["variables"] = json.dumps(variables)
    return form


def check_response(status: int, text: str = "") -> None:
    lowered = text.lower()
    if status == 429 or any(marker in lowered for marker in (
        '"feedback_required"', '"please wait a few minutes',
    )):
        raise TooManyRequestsException("Following feed rate limited; not retried")
    if status in (401, 403) or any(marker in lowered for marker in (
        '"challenge_required"', '"checkpoint_required"', '"login_required"',
    )):
        raise AbortDownloadException("Following feed challenged or logged out; not retried")
    if status >= 400:
        raise RuntimeError(f"Following feed HTTP {status}; not retried")


@contextmanager
def browser_pages(loader: Any) -> Iterator[Any]:
    """Yield a paced page fetcher; bridge cookies without a second login/profile.

    The headless browser lives only for this run. Replaying the captured query
    from after=null also handles server-preloaded first pages without relying
    on Instagram's internal HTML/Relay bootstrap format.
    """
    try:
        from playwright.sync_api import Error as BrowserError, sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Following mode needs: pip install -r requirements-following.txt; "
            "python -m playwright install chromium"
        ) from exc
    jar = loader.context._session.cookies
    cookies = {}
    for cookie in sorted(jar, key=lambda item: bool(item.domain)):
        domain = cookie.domain.lstrip(".")
        if domain and domain != "instagram.com" and not domain.endswith(".instagram.com"):
            continue
        cookies[cookie.name] = {
            "name": cookie.name, "value": cookie.value,
            "domain": ".instagram.com", "path": "/", "secure": True,
        }
    if not cookies.get("sessionid", {}).get("value"):
        raise LoginRequiredException("Following feed requires a saved authenticated session")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        try:
            context.add_cookies(list(cookies.values()))
            page = context.new_page()
            captured: list[tuple[str, dict[str, str], dict[str, str]]] = []
            errors: list[Exception] = []

            def intercept(route: Any) -> None:
                if errors:
                    route.abort()
                    return
                request = route.request
                # Some browser telemetry has a binary/compressed POST body.
                # Reading post_data on those raises before we can check its URL.
                template = (request_template(request.url, request.post_data)
                            if request.method == "POST" and is_graphql_url(request.url) else None)
                if template is not None:
                    if not captured:
                        captured.append((request.url, template, request.all_headers()))
                    route.abort()
                elif request.resource_type in ("image", "media", "font"):
                    route.abort()
                else:
                    route.continue_()

            def observe(response: Any) -> None:
                if urlparse(response.url).hostname != "www.instagram.com":
                    return
                try:
                    check_response(response.status)
                    if is_graphql_url(response.url) or urlparse(response.url).path.startswith("/api/v1/"):
                        check_response(response.status, response.text())
                except (AbortDownloadException, TooManyRequestsException) as exc:
                    errors.append(exc)
                except (RuntimeError, BrowserError):
                    pass

            page.route("**/*", intercept)
            page.on("response", observe)
            page.goto(URL, wait_until="domcontentloaded", timeout=45000)
            deadline = time.monotonic() + 45
            while not captured:
                if errors:
                    raise errors[0]
                if any(part in urlparse(page.url).path for part in ("/accounts/login", "/challenge", "/checkpoint")):
                    raise LoginRequiredException("Following browser redirected to login/challenge")
                if time.monotonic() >= deadline:
                    raise RuntimeError("Browser did not issue a verifiable Following query; progress retained")
                page.mouse.wheel(0, 1400)
                page.wait_for_timeout(1500)
            if errors:
                raise errors[0]
            endpoint, template, observed_headers = captured[0]
            # Retain browser query headers, but let the context supply current cookies.
            headers = {key: value for key, value in observed_headers.items()
                       if key.lower() in ("content-type", "x-csrftoken", "x-ig-app-id",
                                          "x-fb-lsd", "x-asbd-id", "x-ig-www-claim",
                                          "x-fb-friendly-name", "origin", "referer")}
            page.unroute_all(behavior="ignoreErrors")
            page.close()  # No background timeline requests while replaying pages.

            def fetch(cursor: str | None) -> dict[str, Any]:
                loader.context._rate_controller.wait_before_query("following")
                for cookie in context.cookies(URL):
                    if cookie["name"] == "csrftoken":
                        headers["x-csrftoken"] = cookie["value"]
                response = context.request.post(
                    endpoint, form=page_form(template, cursor), headers=headers,
                    timeout=45000, max_redirects=0,
                )
                try:
                    text = response.text()
                    check_response(response.status, text)
                    if 300 <= response.status < 400:
                        raise LoginRequiredException("Following query redirected; session needs attention")
                    payload = json.loads(text.removeprefix("for (;;);"))
                    if not isinstance(payload, dict) or payload.get("errors"):
                        raise RuntimeError("Following GraphQL response contains errors; progress retained")
                    return payload
                finally:
                    response.dispose()

            yield fetch
        except BrowserError as exc:
            # Playwright API errors may include all request headers in their
            # diagnostic call log. Never send those session tokens to our logs.
            raise RuntimeError(
                f"Following browser transport failed ({type(exc).__name__}); progress retained"
            ) from None
        finally:
            # Keep rotated cookies in the existing session persistence lifecycle.
            # Do not save a browser profile or print cookies/request tokens.
            try:
                for cookie in context.cookies(URL):
                    if cookie["name"] in cookies:
                        for old in list(jar):
                            if old.name == cookie["name"]:
                                jar.clear(old.domain, old.path, old.name)
                        jar.set(cookie["name"], cookie["value"], domain=".instagram.com", path="/")
            finally:
                context.close()
                browser.close()


def parse_page(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], bool, str | None]:
    if payload.get("errors"):
        raise RuntimeError("Following GraphQL response contains errors")
    connection = (payload.get("data") or {}).get(CONNECTION)
    if not isinstance(connection, dict):
        raise RuntimeError("Missing Following timeline connection")
    edges, info = connection.get("edges"), connection.get("page_info")
    if not isinstance(edges, list) or not isinstance(info, dict) or not isinstance(info.get("has_next_page"), bool):
        raise RuntimeError("Malformed Following page/cursor metadata")
    cursor = info.get("end_cursor")
    if info["has_next_page"] and (not isinstance(cursor, str) or not cursor):
        raise RuntimeError("Following page is missing its next cursor")
    media = []
    for edge in edges:
        node = edge.get("node") if isinstance(edge, dict) else None
        if not isinstance(node, dict):
            raise RuntimeError("Malformed Following edge")
        # Never recurse into recommendations after the end-of-feed demarcator.
        if any(node.get(key) for key in ("ad", "suggested_users", "explore_story", "end_of_feed_demarcator")):
            continue
        item = node.get("media")
        if item is not None:
            if not isinstance(item, dict):
                raise RuntimeError("Malformed Following media")
            if not (item.get("ad_id") or item.get("is_sponsored") or item.get("product_type") == "ad"):
                media.append(item)
        elif not any(key in node for key in ("media", "ad", "suggested_users", "explore_story", "end_of_feed_demarcator")):
            raise RuntimeError("Unknown Following edge type; progress retained")
    return media, info["has_next_page"], cursor


def owner_of(item: dict[str, Any]) -> dict[str, Any]:
    owner = item.get("user") or item.get("owner")
    if not isinstance(owner, dict) or not (owner.get("pk") or owner.get("id")):
        raise RuntimeError("Following media has no verifiable owner ID")
    return owner


def member_handles(item: dict[str, Any], roster: dict[str, str]) -> list[str]:
    owner = owner_of(item)
    coauthors = item.get("coauthor_producers") or []
    if not isinstance(coauthors, list):
        raise RuntimeError("Malformed Following coauthors")
    members = [owner] + coauthors
    return sorted({roster[str(member.get("pk") or member.get("id"))]
                   for member in members if isinstance(member, dict)
                   and str(member.get("pk") or member.get("id")) in roster})


def serialize_media(item: dict[str, Any], handle: str, now: datetime) -> dict[str, Any]:
    """Build the existing archive record without lazy per-post HTTP fetches."""
    owner = owner_of(item)
    media_id = str(item["pk"])
    code = item["code"]
    kind = {1: "GraphImage", 2: "GraphVideo", 8: "GraphSidecar"}[item["media_type"]]
    slides = item.get("carousel_media") if kind == "GraphSidecar" else [item]
    if not isinstance(slides, list) or not slides or not media_id.isdigit() or not code:
        raise RuntimeError("Following media is missing its ID or slides")
    entries = []
    for index, slide in enumerate(slides):
        candidates = (slide.get("image_versions2") or {}).get("candidates") or []
        url = candidates[0].get("url") if candidates else None
        if not isinstance(url, str) or not url.startswith("https://"):
            raise RuntimeError("Following slide is missing its image/cover URL")
        entries.append({"index": index, "is_video": slide["media_type"] == 2,
                        "image_url": url, "media_key": media_key(url) or f"{media_id}_{index}"})
    # Missing caption is different from an explicitly empty caption: never erase
    # archived evidence because a query projection changed.
    caption_node = item["caption"]
    if caption_node is not None and (not isinstance(caption_node, dict)
                                     or not isinstance(caption_node.get("text"), str)):
        raise RuntimeError("Malformed Following caption")
    caption = caption_node.get("text") if caption_node is not None else None
    return {
        "media_id": media_id, "handle": handle,
        "owner_username": str(owner["username"]).lower(),
        "owner_userid": owner.get("pk") or owner.get("id"),
        "shortcode": code, "permalink": f"https://www.instagram.com/p/{code}/",
        "posted_at": iso(datetime.fromtimestamp(item["taken_at"], timezone.utc)),
        "typename": kind, "caption": caption,
        "caption_mentions": sorted(set(re.findall(r"@([a-zA-Z0-9._]+)", caption or ""))),
        "media": entries, "has_video": any(slide["is_video"] for slide in entries),
        "fetched_at": iso(now),
    }


def scope_key(accounts: list[dict[str, Any]], checkpoints: dict[str, Any], viewer: str) -> str:
    scope = [viewer, sorted((a["handle"], str(a["instagram_user_id"]),
                             checkpoints[a["handle"]]["activated_at"]) for a in accounts)]
    return hashlib.sha256(json.dumps(scope).encode()).hexdigest()


def load_state() -> dict[str, Any]:
    try:
        saved = read_json(FOLLOWING_CHECKPOINT_FILE)
        return saved if isinstance(saved, dict) else {}
    except (OSError, ValueError):
        return {}


def select_reconciliation(accounts: list[dict[str, Any]], checkpoints: dict[str, Any], count: int) -> list[dict[str, Any]]:
    """Oldest attempt first, so one unreadable profile cannot starve the roster."""
    beginning = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(accounts, key=lambda a: (
        parse_instant(checkpoints[a["handle"]].get("last_scan_at")) or beginning,
        a["handle"],
    ))[:count]


def collect(loader: Any, accounts: list[dict[str, Any]], checkpoints: dict[str, Any], now: datetime,
            *, max_pages: int = MAX_PAGES) -> dict[str, Any]:
    # Import here to keep the transport independent of collector initialization.
    from scrape_posts import scan_boundary, write_post, write_remote_posts

    if not accounts:
        raise RuntimeError("Following discovery requires a nonempty roster")
    if any(not a.get("instagram_user_id") for a in accounts):
        raise ValueError("Following discovery requires stored IDs for every account; run resolve_ids.py")
    roster = {str(a["instagram_user_id"]): a["handle"] for a in accounts}
    scope = scope_key(accounts, checkpoints, str(loader.context.username))
    state = load_state()
    prior = parse_instant(state.get("observed_through")) if state.get("scope") == scope else None
    boundary = (max(min(parse_instant(c["activated_at"]) for c in checkpoints.values()),
                    prior - timedelta(days=POST_OVERLAP_DAYS)) if prior else
                min(scan_boundary(c, now) for c in checkpoints.values()))
    totals = {"pages": 0, "scanned": 0, "discovered": 0, "updated": 0, "unchanged": 0,
              "media_ids": [], "boundary": iso(boundary)}
    cursor = None
    cursors: set[str] = set()
    seen: set[str] = set()
    old_pages = 0
    ordered = True
    previous: datetime | None = None
    started = time.monotonic()
    with browser_pages(loader) as fetch:
        for _ in range(max_pages):
            items, more, next_cursor = parse_page(fetch(cursor))
            totals["pages"] += 1
            if more and next_cursor in cursors:
                raise RuntimeError("Following cursor repeated; progress retained")
            records = []
            dates = []
            for item in items:
                media_id = str(item["pk"])
                if media_id in seen:
                    continue
                seen.add(media_id)
                published = datetime.fromtimestamp(item["taken_at"], timezone.utc)
                if previous is not None and published > previous:
                    ordered = False
                previous = published
                dates.append(published)
                handles = member_handles(item, roster)
                if published < boundary:
                    continue
                # One media ID has one durable archive owner; prefer original
                # author if in the roster, otherwise a stable accepted coauthor.
                owner = owner_of(item)
                owner_handle = roster.get(str(owner.get("pk") or owner.get("id")))
                eligible = [h for h in handles if published >= parse_instant(checkpoints[h]["activated_at"])]
                if not eligible:
                    continue
                handle = owner_handle if owner_handle in eligible else eligible[0]
                record = serialize_media(item, handle, now)
                records.append(record)
                outcome = write_post(record)
                totals[{"new": "discovered", "updated": "updated", "unchanged": "unchanged"}[outcome]] += 1
                totals["scanned"] += 1
                totals["media_ids"].append(media_id)
            # Mirror every page. A later failure leaves earlier records useful,
            # but never advances the Following watermark or profile checkpoints.
            write_remote_posts(records)
            old_pages = old_pages + 1 if dates and all(d < boundary for d in dates) else 0
            if not more or (ordered and old_pages >= 2):
                break
            cursors.add(next_cursor)
            cursor = next_cursor
        else:
            raise RuntimeError(f"Following page budget ({max_pages}) exhausted; progress retained")
    # This means the observed timeline was traversed, not all profiles covered.
    write_json(FOLLOWING_CHECKPOINT_FILE, {"scope": scope, "observed_through": iso(now)})
    log.info("Following: %d pages, %d posts, %d new in %.1fs (ordered=%s)",
             totals["pages"], totals["scanned"], totals["discovered"], time.monotonic() - started, ordered)
    return totals
