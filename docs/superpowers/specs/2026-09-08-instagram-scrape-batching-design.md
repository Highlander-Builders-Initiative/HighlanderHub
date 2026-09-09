# Instagram Scrape Batching

## Goal

Make `scrape.py` sustainable at daily-or-better cadence now that
`accounts.json` holds 841 accounts, without inviting rate limiting or account
termination. Batch the story fetch so request volume tracks content volume
instead of account-list size, and stop discarding the story link data that
`rsvp_url` depends on.

## Problem

`scrape_account` calls `L.get_stories(userids=[one_id])` once per account, so a
run issues 841 separate `reels_media` GraphQL requests. Simulating
instaloader's own `RateController` against the current
`time.sleep(random.uniform(2.0, 5.0))` puts a run at roughly 60 minutes. The
rate controller never engages: a 3.5s mean sleep is already slower than its cap
of 200 queries per 11 minutes.

Runtime is the visible symptom; request volume is the actual risk. 841
single-user story queries in an hour is a pattern no real Instagram client
produces.

The volume is also almost entirely wasted. Across 26 days of scrapes in
`data/raw/`, the median day had 9 distinct handles post a story and the busiest
had 22, against 416 accounts configured at the time. Over 95% of requests
return nothing.

Profile resolution is not part of the problem. All 841 accounts carry an
`instagram_user_id`, so `_resolve_profile` already performs zero network calls.

## Approach

Invert the loop: iterate chunks of 50 accounts and ask about all of them in one
request.

```
main()
  ├─ _login(L)
  ├─ accounts = _load_scrape_accounts(L)             # unchanged
  ├─ batchable, by_userid, skipped = _index_by_userid(accounts)
  │     # batchable: ordered accounts holding an instagram_user_id
  │     # by_userid: {instagram_user_id: account} for reverse lookup
  │     # skipped:   accounts missing an id
  ├─ for chunk in _chunks(batchable, size=STORY_CHUNK_SIZE):
  │     ├─ scrape_chunk(L, chunk, by_userid)         # 1 GraphQL request
  │     └─ sleep(uniform(5, 15))                     # jitter moves here
  └─ _persist_rotated_session(L)                     # unchanged
```

`scrape_account` becomes `scrape_chunk`, passing up to 50 userids per
`get_stories()` call. Instagram's `reels_media` only returns entries for
accounts with live stories, so a 50-account chunk typically yields two or three
`Story` objects.

This drops a run to 17 GraphQL requests plus one iphone-API request per
account that actually has stories — roughly 40 to 55 requests and 4 minutes,
against ~870 requests and ~60 minutes today. That finally makes the 4–6× daily cadence
the README recommends realistic: six runs a day would stay under half of one
current run's request volume.

### Chunking is ours, not instaloader's

`get_stories` accepts a userid list and already chunks it 50-per-query
internally, but its `_userid_chunks` is a generator: a failure on chunk 7 kills
the iterator and silently loses chunks 8 through 17 with no way to resume.
Chunking in `scrape.py` gives per-chunk error handling, per-chunk jitter, and
the split-retry behavior below.

`STORY_CHUNK_SIZE` stays at 50 to match instaloader's internal default, keeping
the request shape identical to what Instagram already expects from a large
installed base. URL length is not the constraint — `graphql_query` sends
variables as a URL-encoded JSON GET parameter, and 50 of these userids (7–11
digits) produce an 836-character URL. Instagram's server-side cap on `reel_ids`
is undocumented, so the constant is not a tuning knob; raising it is
unvalidated and moves further from real client behavior for no gain.

### Mapping stories back to accounts

Without a per-account loop, each returned `Story` must be mapped to its
account. `story.owner_id`, `story.owner_username`, and `story.itemcount` are
all network-free — they read off the already-fetched reels response — so
`_index_by_userid` plus an `owner_id` lookup costs nothing.

The handle used for `data/raw/<handle>/` comes from the accounts list via
`owner_id`, never from `story.owner_username`. `normalize.py` joins on that
handle to attach `label` and `account_category`, and the existing 71 raw
directories are already named that way. Trusting `owner_username` would start a
second orphan directory for any club that renamed itself.

When `story.owner_username` disagrees with the stored handle, that is a handle
rename and gets a warning. `permalink` construction depends on the current
handle, and there is no detection for this today.

Duplicate `instagram_user_id` values across accounts warrant a warning naming
both handles, keeping the first — an ambiguous userid otherwise makes the
output directory nondeterministic.

Accounts absent from a chunk's response simply have no live stories. They are
counted in an aggregate, not logged per account.

### Accounts without a userid

Batching requires a known `instagram_user_id`. Accounts lacking one are skipped
with a loud warning naming each handle, counted in the run totals, and the
README documents running `resolve_ids.py` after editing `accounts.json`.

`_resolve_profile`'s search and GraphQL fallbacks are removed. That path was
itself a per-account network call — the exact cost this change exists to
eliminate — and `resolve_ids.py` is already the dedicated tool for filling the
field in bulk.

## Error Isolation

When a chunk returns a bad request, split it in half and retry each half,
recursing to size 1. One mechanism covers two distinct failures:

- **A poison userid** (deleted, banned, or mistyped) is isolated in about 12
  requests worst case instead of costing 50 accounts their run. Exactly one
  leaf fails at size 1, and the log names the handle so the `accounts.json`
  entry can be pruned.
- **A chunk-size cap below 50**, if Instagram enforces one, degrades
  automatically. A cap of 20 would fail at 50, fail at 25, and succeed near 12.
  The effective working size is logged once so `STORY_CHUNK_SIZE` can be
  lowered to match.

The two cases are distinguishable and the logs must say which was seen: a
single failing leaf means a bad account, whereas every chunk above some size
failing means a cap.

This tightens the fatal condition rather than loosening it. Today
`InstagramStoriesBadRequest` treats the *first* 400 as fatal and ends the run,
on the reasoning that a 400 means a dead session that will repeat for every
account. That costs a whole day's scrape to one bad account. Under split-retry
the fatal condition becomes precise: if the split reaches size 1 and every
individual request still fails, the session is dead and the run aborts with the
existing loud error. A single bad userid among 841 no longer stops the run.

The existing `ProfileNotExistsException` and all-profiles-missing session check
lose their meaning once profiles are never fetched individually. The equivalent
signal under batching is every chunk failing down to singletons, which the
split-retry already reports.

## Story Link Extraction

`_serialize_item` reads `getattr(item, "story_cta_url", None)`. `StoryItem` has
no such property, and instaloader contains no `story_cta`,
`story_link_stickers`, `webUri`, or `link_sticker` references anywhere, so the
field has been `None` for all 690 archived stories.

This was not a cosmetic gap. With link stickers missing and Gemini preferred
by the mapper, every published RSVP link came from Gemini reading a URL out of OCR'd
flyer pixels rather than from the link the club actually attached. Link
stickers are ground truth; OCR'd URLs are the most error-prone field to
recover from an image. The mapper now normalizes the CTA first, falling back
to independently normalized Gemini output if the CTA is absent or invalid.

The link is available at no extra request cost. `Story.get_items()` already
fetches the iphone struct once per account and stitches each item's struct into
the node before constructing the `StoryItem`, so `item._iphone_struct` is
already populated.

A `_story_cta_url(item)` helper reads it, checking both shapes Instagram uses:

- `story_link_stickers[].story_link.url` — link stickers, which replaced
  swipe-up in 2021 and are what clubs use today.
- `story_cta[].links[].webUri` — the legacy swipe-up field.

These URLs arrive wrapped as `l.instagram.com/?u=<urlencoded-target>`, so the
helper unwraps to the real destination; storing the wrapper would put an
expiring Instagram redirect into every `rsvp_url`. The helper catches
`IPhoneSupportDisabledException` and `KeyError` and returns `None`, so a
missing or restructured struct never breaks a scrape.

`iphone_support` stays enabled. `StoryItem.url` and `video_url` prefer
iphone-struct URLs for full-resolution media, and the cost is one request per
account that has stories — 20 to 40 per day, bounded by content volume rather
than list size, and well inside the 199-per-30-minutes iphone window.

No schema work is required. `schemas/stories.upsert.schema.json`, the
`story_cta_url text` column in `20260513073310_init_schema.sql`, and
`src/lib/supabase-rows.ts` already carry the field.

## Tests

The `story_cta_url` bug survived because
`test_scrape_account_uses_instaloader_stories_api` asserts against a `Mock`
that fabricates any attribute assigned to it, including one instaloader does
not define. The test verifies a field it invented. Every `Mock`-based assertion
about instaloader's interface in `test_scrape.py` shares that blind spot.

Tests move to JSON fixtures shaped like real `reels_media` responses in the
existing `tests/fixtures/`, driven through the real `Story` and `StoryItem`
classes so the interface is exercised rather than imagined. Coverage:

- a chunk mixing productive and silent accounts, asserting per-handle writes
  and aggregate counts;
- `owner_id`-to-handle mapping, including a duplicate userid warning;
- an `owner_username` mismatch raising the rename warning;
- split-retry converging on a single poison userid inside a healthy chunk;
- every singleton failing, producing the session-death abort;
- a chunk-size cap, producing successful smaller chunks and the effective-size
  log;
- accounts missing `instagram_user_id` skipped, warned, and counted;
- CTA extraction for link-sticker and legacy swipe-up shapes, the
  `l.instagram.com` unwrap, and a struct with no link returning `None`.

Session handling tests (`_login`, `_persist_rotated_session`) and the
followed-accounts tests are unaffected and stay as they are.

## Follow-up: Tray-Based Scraping

Recorded as the endgame, not built here.

`get_stories()` with no arguments reads the reels tray, which names exactly
which accounts have live stories in a single request. That is both the cheapest
possible steady state and the lowest-fingerprint option, because requesting
reels only for accounts you follow is what a real client does.

Batching reduces request count but does not fix request *shape*: asking for 50
non-followed accounts' reels still describes a pattern no human client
produces. Whether fewer, larger, unusual requests beat many small ones is an
empirical question about Instagram's detection that cannot be settled from
instaloader's source. This is the main argument for the follow-up.

The blocker is that the tray only sees followed accounts, and `accounts.json`
is curated largely independently of the scraper account's follow graph.
Bulk-following 841 accounts is itself heavily rate-limited and is a reliable
way to trigger the termination this work avoids, so it requires a ramp of
roughly 20–50 follows per day over several weeks.

Two unknowns to resolve before trusting it:

- The tray may be ranked or truncated by Instagram, so it needs reconciling
  against a periodic full batched sweep before it can be the only mechanism.
- The README already documents the follow-list GraphQL call failing on
  imported Safari sessions, which suggests the tray query may fail the same
  way and need the same fallback.

Because of both, the tray composes with this work rather than replacing it:
tray for followed accounts, batched sweep for the rest and as reconciliation.
The chunking built here stays load-bearing either way.

## Out of Scope

No changes to `extract_stories.py`, `normalize.py`, the raw file layout, the
Supabase row shapes, or the launchd schedule. Raw output stays at
`data/raw/<handle>/<item_id>.json` and stays idempotent, so the existing
archive and all downstream stages are unaffected. Changing run cadence is
enabled by this work but is a separate decision.
