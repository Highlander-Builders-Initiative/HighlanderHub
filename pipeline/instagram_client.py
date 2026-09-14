"""Instagram session, request pacing, and account roster helpers."""
from __future__ import annotations

import logging
import random
from typing import Any

import instaloader
from instaloader.exceptions import (
    ConnectionException,
    QueryReturnedBadRequestException,
    TooManyRequestsException,
)

import instagram_cooldown
from accounts import uses_followed_accounts
from config import (ACCOUNT_SOURCE, FOLLOWED_ACCOUNTS_FILE, IG_PASSWORD, IG_USERNAME,
                    SESSION_FILE, load_curated_accounts, load_followed_accounts_cache,
                    write_followed_accounts_cache)
log = logging.getLogger("pipeline.instagram_client")
REQUEST_GAP_RANGE = (1.0, 2.5)
# Headers that distinguish throttling and challenges from ordinary HTTP errors.
_DIAGNOSTIC_HEADERS = (
    "retry-after",
    "x-ratelimit-remaining",
    "x-fb-rlafr",
    "www-authenticate",
    "x-ig-set-www-claim",
    "content-type",
)


class PacedRateController(instaloader.RateController):
    """Instaloader's rate controller with a floor between consecutive requests."""

    def wait_before_query(self, query_type: str) -> None:
        self.sleep(random.uniform(*REQUEST_GAP_RANGE))
        super().wait_before_query(query_type)

    def handle_429(self, query_type: str) -> None:
        # Instaloader's default sits out its sliding window and asks again, up to
        # twice more. A 429 means stop, not wait: raise it so the collector
        # pauses collection instead.
        raise TooManyRequestsException(f"429 Too Many Requests on {query_type}; not retried")


def _log_http_errors(resp: Any, *args: Any, **kwargs: Any) -> Any:
    """requests response hook: dump the real status code, the headers that
    reveal throttling/challenge state, and the response body for any 4xx/5xx
    Instagram returns. This makes a 400 diagnosable (malformed query vs. rate
    limit vs. checkpoint) instead of guessing from the generic 'bad request'.
    """
    if resp.status_code < 400:
        return resp
    headers = {
        k: v for k, v in resp.headers.items() if k.lower() in _DIAGNOSTIC_HEADERS
    }
    body = resp.text[:1000]
    truncated = "… (truncated)" if len(resp.text) > 1000 else ""
    log.warning(
        "Instagram HTTP %s %s on %s\n  diagnostic headers: %s\n  body: %s%s",
        resp.status_code,
        resp.reason,
        resp.url,
        headers,
        body,
        truncated,
    )
    return resp


def _attach_http_error_logger(L: instaloader.Instaloader) -> None:
    session = getattr(getattr(L, "context", None), "_session", None)
    hooks = getattr(session, "hooks", None)
    if not isinstance(hooks, dict):
        return

    response_hooks = hooks.setdefault("response", [])
    if hasattr(response_hooks, "append") and _log_http_errors not in response_hooks:
        response_hooks.append(_log_http_errors)


def _login(L: instaloader.Instaloader) -> None:
    if SESSION_FILE:
        # Session file produced by `instaloader -l <user>`; safer for unattended runs.
        L.load_session_from_file(IG_USERNAME or "", SESSION_FILE)
        log.info("Loaded session from %s", SESSION_FILE)
        # Bypassing strict L.test_login() check because Instagram's test query hash
        # is heavily rate-limited on CI environments (e.g. GitHub Actions).
        # Any actual session expiration will be caught during the scraping requests.
        return
    if not IG_USERNAME or not IG_PASSWORD:
        raise SystemExit(
            "Instagram credentials required. Set IG_USERNAME + IG_PASSWORD, "
            "or IG_SESSION_FILE pointing to a session created by "
            "`instaloader -l <user>`."
        )
    L.login(IG_USERNAME, IG_PASSWORD)
    log.info("Logged in as %s", IG_USERNAME)


def _cookie_jar(L: instaloader.Instaloader) -> Any:
    session = getattr(getattr(L, "context", None), "_session", None)
    return getattr(session, "cookies", None)


def _current_sessionid(L: instaloader.Instaloader) -> str | None:
    """Return the live `sessionid` cookie value from the in-memory jar, if any.

    The same live session shows up under two domains. A `sessionid` Instagram
    rotates in mid-run arrives via Set-Cookie scoped to `.instagram.com`, but
    one loaded from SESSION_FILE has no domain at all — instaloader rebuilds
    the jar with `requests.utils.cookiejar_from_dict`, which defaults the
    domain to "". Accepting only the scoped form declared every unrotated run
    logged out, which is common for sessions loaded from disk. Prefer the rotated
    value when both are present.
    """
    cookies = _cookie_jar(L)
    if cookies is None:
        return None

    from_file: str | None = None
    for cookie in cookies:
        if cookie.name != "sessionid" or not cookie.value:
            continue
        if str(getattr(cookie, "domain", "") or "").endswith("instagram.com"):
            return cookie.value
        from_file = cookie.value
    return from_file


def _persist_rotated_session(L: instaloader.Instaloader) -> None:
    """Write the (possibly rotated) session cookies back to SESSION_FILE.

    Instagram rotates `sessionid` via Set-Cookie as the session is used, but we
    only ever loaded a snapshot at startup and never saved the rotated jar back.
    Every run therefore replayed an aging snapshot until it went stale — which
    happens within a day or two when the same account is also live in a browser
    that rotates the shared cookie out from under the on-disk copy. Persisting the
    rotated jar after each run keeps the file current so the session survives.

    Guards (mirrors import_safari_session.py so a dead run can't clobber a good
    file):
      * Only writes in session-file mode (IG_SESSION_FILE configured).
      * Refuses to overwrite when the jar has no `sessionid` (logged-out/expired).
      * Never raises — persistence must not mask the scrape's own result.
    """
    if not SESSION_FILE:
        return
    try:
        sessionid = _current_sessionid(L)
        if not sessionid:
            names = sorted(
                {cookie.name for cookie in _cookie_jar(L) or [] if cookie.value}
            )
            log.warning(
                "Not saving session back to %s: no sessionid cookie with a value "
                "(session looks logged out/expired). Left the file untouched. "
                "Cookies in the jar: %s",
                SESSION_FILE,
                ", ".join(names) or "none",
            )
            return
        L.save_session_to_file(SESSION_FILE)
        log.info("Saved rotated session back to %s", SESSION_FILE)
    except Exception as e:  # noqa: BLE001 — persistence must never break the run
        log.warning("Could not persist rotated session to %s: %s", SESSION_FILE, e)


def _profile_username(profile: instaloader.Profile) -> str:
    return str(getattr(profile, "username", "") or "").strip()


def _account_from_followed_profile(
    profile: instaloader.Profile,
    curated_by_handle: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    handle = _profile_username(profile)
    existing = curated_by_handle.get(handle.lower(), {})
    account = dict(existing)
    account["handle"] = handle

    if not account.get("label"):
        account["label"] = str(getattr(profile, "full_name", "") or handle)

    user_id = getattr(profile, "userid", None)
    if user_id is not None:
        try:
            account["instagram_user_id"] = int(user_id)
        except (TypeError, ValueError):
            log.warning("%s: followed profile had invalid userid: %r", handle, user_id)

    account["account_source"] = "instagram_followed"
    return account, bool(existing)


def _load_followed_accounts(
    L: instaloader.Instaloader,
    curated_accounts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    username = IG_USERNAME or str(getattr(L.context, "username", "") or "")
    if not username:
        raise RuntimeError(
            "IG_USERNAME is required when PIPELINE_ACCOUNT_SOURCE=followed so "
            "the scraper can enumerate the logged-in account's follow list."
        )

    viewer = instaloader.Profile.from_username(L.context, username)
    curated_by_handle = {
        str(account.get("handle", "")).lower(): account
        for account in curated_accounts
        if account.get("handle")
    }
    by_handle: dict[str, dict[str, Any]] = {}
    matched_curated = 0

    for profile in viewer.get_followees():
        handle = _profile_username(profile)
        if not handle:
            continue
        account, matched = _account_from_followed_profile(profile, curated_by_handle)
        by_handle[handle.lower()] = account
        if matched:
            matched_curated += 1

    accounts = sorted(by_handle.values(), key=lambda account: account["handle"].lower())
    return accounts, matched_curated


def _load_scrape_accounts(L: instaloader.Instaloader) -> list[dict[str, Any]]:
    curated_accounts = load_curated_accounts()
    if not uses_followed_accounts(ACCOUNT_SOURCE):
        log.info("Account source: accounts.json (%d accounts)", len(curated_accounts))
        return curated_accounts

    try:
        accounts, matched_curated = _load_followed_accounts(L, curated_accounts)
    except (QueryReturnedBadRequestException, ConnectionException) as e:
        if instagram_cooldown.classify(e) is not None:
            # Pushback rather than the follow-list quirk below: carrying on from
            # the cache would send the post fetch straight into it.
            raise
        log.warning(
            "Could not fetch Instagram follow list (%s). Imported/Safari sessions "
            "often fail this GraphQL call; using follow cache or accounts.json.",
            e,
        )
        cached = load_followed_accounts_cache()
        if cached:
            log.info(
                "Account source: followed-account cache (%d accounts) from %s",
                len(cached),
                FOLLOWED_ACCOUNTS_FILE,
            )
            return cached
        log.warning(
            "No followed-account cache; falling back to accounts.json (%d accounts)",
            len(curated_accounts),
        )
        return curated_accounts

    if not accounts:
        raise RuntimeError(
            "Instagram returned zero followed accounts; refusing to replace the "
            "runtime account cache. Check the scraper account's follow list and "
            "session health."
        )
    write_followed_accounts_cache(accounts)
    log.info(
        "Account source: followed accounts (%d accounts; %d matched accounts.json "
        "metadata; cache=%s)",
        len(accounts),
        matched_curated,
        FOLLOWED_ACCOUNTS_FILE,
    )
    return accounts
