# Event ingestion pipeline

Collect campus events from Instagram feed posts. Instagram captions and carousel images become source
text through OCR, then grounded semantic assessment produces event rows.

`run.py` executes four isolated stages: `instagram.posts.scrape`,
`instagram.posts.extract`, `instagram.publish`, and `events.reconcile`.
Collection failures still allow extraction and publication of archived posts.
Each run records stage status and duration in `data/run_history.jsonl`.

## Layout

| Module | Responsibility |
| --- | --- |
| `instagram_client.py` | Login, session persistence, request pacing, account roster |
| `scrape_posts.py` | Feed collection and checkpoint management |
| `instagram_cooldown.py` | Persisted collection pauses |
| `post_archive.py` | Local and durable post archive |
| `image_ocr.py` | Image downloads and Google Vision OCR |
| `extract_posts.py` | Per-slide OCR and QR cache |
| `event_dates.py` | Printed date and time evidence |
| `instagram_rows.py` | Instagram event row policy |
| `content_assessment.py` | Grounded semantic assessment |
| `assessed_events.py` | Source publication and reassessment |
| `reconcile_events.py` | Cross-source deduplication and notifications |

Archives and caches under `data/` are gitignored. Posts live in
`data/posts/`, OCR in `data/post_extractions/`, and assessments in
`data/assessments/`.

## Setup

```bash
cd pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Auth

Instagram requires a logged-in session to fetch posts. Pick one:

**Option A — session file (recommended for cron):**

```bash
instaloader -l your_ig_username        # prompts password + 2FA, writes ~/.config/instaloader/session-...
export IG_USERNAME=your_ig_username
export IG_SESSION_FILE=$HOME/.config/instaloader/session-your_ig_username
```

Or, if `instaloader -l` hits 401 / rate limits, log into Instagram in **Safari**,
grant Terminal **Full Disk Access**, then:

```bash
# edits username in import_safari_session.py, writes ~/.config/instaloader/session-<user>
.venv/bin/python import_safari_session.py
```

Put the **file path** (not base64) in `pipeline/.env`:

```bash
IG_USERNAME=rhino.5172250
IG_SESSION_FILE=$HOME/.config/instaloader/session-rhino.5172250
```

(`base64 -i …` is only for the GitHub Actions secret `IG_SESSION_FILE_B64`.)

If login succeeds but scrape dies on `get_followees` / `400 invalid request`, the
the follow-list GraphQL call failed; this alone does not establish
whether feed collection will succeed. The scraper falls back to `data/followed_accounts.json`, then
`accounts.json`. To skip the follow-list call entirely:

```bash
PIPELINE_ACCOUNT_SOURCE=accounts_json
```

**Option B — username + password env vars (interactive 2FA):**

```bash
export IG_USERNAME=your_ig_username
export IG_PASSWORD=...
```

Use a **dedicated account**, not your personal one. Instagram is aggressive
about flagging accounts that look like scrapers — expect occasional
checkpoints / temporary blocks, and add jitter / lower the cadence if you
get throttled. Every Instagram request waits an extra 1–2.5s
(`REQUEST_GAP_RANGE`), and `scrape_posts.py` sleeps 5–12s between accounts.

## Editing accounts.json

`scrape_posts.py` validates feed ownership against the stored numeric user ID,
so every entry needs an `instagram_user_id`. New handles added by hand need one:

```bash
python resolve_ids.py          # fills in every account missing an id
python resolve_ids.py --dry-run
```

Accounts still missing an id are skipped by the scrape and named in a warning —
they are invisible to the run until resolved.

Supabase writes and post extraction also need credentials in `pipeline/.env`:

```bash
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
DISCORD_WEBHOOK_URL=...
GOOGLE_VISION_API_KEY=...
GEMINI_API_KEY=...
GOOGLE_CLOUD_PROJECT=...
GOOGLE_CLOUD_LOCATION=global
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

Assessment uses the Gemini API when `GEMINI_API_KEY` is set, and billed Vertex AI
otherwise. Create the key in AI Studio under a project with no billing account so
it stays on the free tier: no charge, but Google may use the prompts to improve its
products, and requests are capped per minute and per day. Calls are spaced to
`FREE_TIER_RPM` in `content_assessment.py`. A quota failure stops assessment and publishes completed results; it does not
automatically switch to billed Vertex AI. Run with `GEMINI_API_KEY=` to skip the free tier entirely.

## Run it

```bash
python run.py

# Individual stages
python scrape_posts.py
python extract_posts.py --no-notify

# Offline tests
.venv/bin/python -m unittest discover -s tests
```

Collection accesses Instagram. Extraction calls Google Vision for uncached
images; assessment calls Gemini when source text changes. Publication writes
to Supabase. `extract_posts.py --dry-run --report /tmp/post-report.json` assesses
and generates reviewable rows without publishing or sending notifications.

## Schedule

The supported unattended runner is
macOS launchd via `install-launchd.sh`, which runs `run_daily.sh` at 07:00
local time. To run more often, point cron at that same wrapper — don't invoke
`run.py` directly (you'd skip log rotation and the failure notification).

### Unattended runs (macOS launchd)

`run_daily.sh` wraps `run.py`: it logs to `pipeline.log` (rotated past 5 MB)
and raises a macOS notification when the run exits nonzero. The install script
writes a plist for *this* checkout (no hardcoded machine path) and loads it.

```
./install-launchd.sh
launchctl start com.highlanderhub.pipeline   # run once now, schedule untouched
```

Uninstall:

```
launchctl unload ~/Library/LaunchAgents/com.highlanderhub.pipeline.plist
```

Run it here rather than in GitHub Actions: the Instagram session survives
locally because the run comes from a residential IP and `scrape_posts.py` writes the
rotated `sessionid` back to `IG_SESSION_FILE` after every run. On a CI runner
that file is ephemeral, so each run replays the same increasingly stale cookie
from `IG_SESSION_FILE_B64` until Instagram rejects it — which is why the cron
in `.github/workflows/scrape.yml` is commented out.

Scheduling cannot renew an expired session. When the Instagram step starts
failing with `400 ... "invalid request"`, quit Safari and re-run
`import_safari_session.py`.

### When Instagram pushes back

A 429, checkpoint, challenge, `feedback_required` reply, logged-out redirect,
HTTP 401/403, or a 400 on a single post request stops collection and records a pause in
`data/instagram_cooldown.json` for `PIPELINE_INSTAGRAM_COOLDOWN_HOURS` (default
24). A 429 is never waited out and retried. Until the pause ends, collection
fails before sending a request. After any collection failure, `run.py` processes
only cached image results for publication, without more Instagram/CDN downloads.
Image HTTP 401/403/429 responses also persist this shared pause.

A successful `import_safari_session.py` run lifts a pause classified as a session
challenge. Rate limits and `feedback_required` action restrictions keep their
original cooldown even after a session refresh, including pauses older runs
misclassified as challenges. The deadline is the collector's waiting period,
not a promise that Instagram will remove its restriction then. A pause file
that can't be read keeps collection paused until you check it and delete it.

### Stopping and resuming an interrupted run

Collection stops at its first operational failure, with one request attempt and
60-second feed timeouts. Ordinary missing/private profiles are still skipped.
OCR/extraction stops at the first failed post and passes its completed results
to publication. Assessment likewise stops at its first service/transport failure
and publishes the completed prefix. Database publication failures leave local
post, OCR, and assessment caches available for the next attempt. No background
retry or automatic wakeup is scheduled.

After a run, inspect `data/last_run.json` for stage outcomes, the failing account
or post, and recovery instructions; `data/run_history.jsonl` keeps prior reports.
Account checkpoints retain `last_error` and normal incremental progress, and
post caches retain per-post failure details. Resolve the reported problem or wait
for the Instagram cooldown, then rerun the same command from the repository root:

```bash
pipeline/.venv/bin/python pipeline/run.py
```

A failed extraction can appear as a successful extraction stage only in older
run reports; the runner now marks it failed while retaining its completed posts
for publication. A completed run exits zero; a blocked or partially failed run
exits nonzero. No requests are made to Instagram to validate the offline tests.

## Supabase row shapes

Cross-language contracts live in [`schemas/`](../schemas/README.md): JSON Schema
for upsert rows, generated `src/lib/supabase-rows.ts`, and contract tests in
`tests/schema-contracts.test.mjs` + `pipeline/tests/test_schema_contract.py`.
Postgres migrations under `supabase/migrations/` remain the database source of
truth.

### `events`

Already in the DB shape that `src/lib/events/index.ts` maps into `CampusEvent`
(see `src/types/event.ts`; row type is `EventRow` in `src/lib/supabase-rows.ts`).

```jsonc
{
  "id": "ig_cyber_ucr_p3980467437204327812",
  "title": "Security Night Workshop",
  "description": "...",
  "starts_at": "2026-05-15T19:00:00-07:00",
  "ends_at": null,
  "location": "Winston Chung Hall",
  "host": "UCR Cybersecurity Club",
  "host_handle": "cyber_ucr",
  "category": "career",
  "tags": ["security", "workshop"],
  "source": "instagram",
  "source_url": "https://www.instagram.com/p/SecurityNight/",
  "image_url": "https://...supabase.co/storage/v1/object/public/event-flyers/instagram/cyber_ucr/posts/3894795737410658765/flyer.jpg",
  "is_free": true,
  "rsvp_required": true,
  "rsvp_url": "https://lu.ma/...",
  "scraped_at": "2026-05-14T12:00:00+00:00"
}
```

## Hand-off to the app

The Next.js app reads upcoming events from the Supabase `events` table via
`src/lib/events/index.ts`. `assessed_events.py` publishes Instagram flyers into that
same table with `source='instagram'`.

If `DISCORD_WEBHOOK_URL` is set, the pipeline posts newly discovered free-food
events to Discord after Supabase upsert. The `discord_notifications` table
records successful sends by a durable `notification_key` based on the public
event identity, so reruns and generated row ID changes do not repost the same
event.

## Instagram post collection

Posts provide persistent captions and flyers for club announcements. `scrape_posts.py` constructs the logged-in GraphQL
`NodeIterator` used by Instaloader 4.15.3's `get_posts()` directly, skipping its
profile-metadata lookup and reading photos and image carousels through
`get_sidecar_nodes()`. Pagination and request pacing stay with Instaloader.
An offline transport regression verifies that the feed request matches the
upstream method, URL, headers, and body; live reliability is not yet verified.

The GraphQL query uses the roster handle. Before accepting a page, every post's
author ID or an accepted `coauthor_producers` ID must match the stored
`instagram_user_id`, including pinned and old posts. Collaborations retain their
original author for event attribution. Pending coauthor invitations and ordinary
tags do not qualify. Missing authors or unverified membership reject the page
and retain the scan checkpoint. An empty first page cannot prove
account identity and also retains the checkpoint, even for a truly empty feed.
Missing IDs require `resolve_ids.py`; there is no automatic profile-lookup fallback.

Normal collection is **forward-only**. Before an account's first fetch the run records
an `activated_at` timestamp, and nothing published before it is ever imported —
including an old post the club pins to the top of its profile later. Activation
is claimed through `claim_post_activation`, which inserts only when absent.
If that claim fails, the local timestamp is retained and retried whenever the
durable row is missing. Progress is mirrored only after the stored activation
matches the scan's boundary. Losing `data/` recovers the durable activation;
if both copies are lost before a claim succeeds, the original boundary cannot
be recovered.

For an opt-in historical maintenance sweep, set this in `pipeline/.env`, then run `run.py`
as usual:

```bash
PIPELINE_POST_BACKFILL_SINCE=2025-08-01
```

This accepts publication times from **August 1, 2025 at 00:00 UTC**, inclusive,
overriding both activation and the recent scan checkpoint. It forces the
`accounts.json` roster and profile discovery, so a normal `run.py` visits every
configured account rather than Following mode's bounded reconciliation batch.
There is no post/page cap. Explicit `scrape_posts.py --handle` filters still
apply; the bounded `--direct-feed` pilot cannot be combined with a backfill.
The normal activation timestamps, pacing, identity checks, and cooldown remain
in place. Private/unreadable accounts can be skipped, and Instagram pushback
still stops collection before the remaining accounts.

**Remove or blank `PIPELINE_POST_BACKFILL_SINCE` after the sweep.** Every run with
this setting enabled scans each selected account from its first page back to the
cutoff, including accounts scanned successfully before. There are no per-account
backfill completion markers; legacy markers are removed when checkpoints are saved.
Unchanged posts and image results still reuse their caches. Failed image downloads
get their post URL refreshed on the next collection run if discovery did not fetch
them. Removing the setting restores normal incremental discovery using the existing
activation timestamps and scan checkpoints.
This changes post collection dates, not event eligibility or publication rules.

Each run re-walks a seven-day overlap behind the last successful scan, bounded
by activation. `Post.is_pinned` is documented upstream as "now likely returns
always false", so pinned entries are handled the way Instaloader's own
downloader handles them: the first three entries never terminate a scan
(`possibly_pinned=3`). They are still collected on their own merits.

A scan walks to its date boundary or the end of the feed, with no fixed post
count cutoff: a busy account must be able to pass the same newest-first prefix
on its next run. A checkpoint advances only after a scan completes **and** its
raw writes reach Supabase. An interrupted scan keeps the items it already
collected locally and re-walks the interval next run. Authentication challenges
and rate limits stop Instagram collection (see
[When Instagram pushes back](#when-instagram-pushes-back)), record incomplete
coverage, and retain every checkpoint — continuing would turn one throttle into
a run-long pattern of rejected requests.

The local archive is a cache of `instagram_posts`, and both collection and
extraction restore it from that mirror before reading it. A machine that lost
`data/` therefore gets back every post the mirror holds, not just the seven days
the next scan re-walks — which is what keeps older posts still supporting live
events being refreshed and reassessed. Restoring fills gaps only: a post already
on disk is preserved so a stale mirror cannot undo a local caption correction.
This restores missing files; it does not synchronize existing files from another
machine or an older backup. It cannot re-admit history either,
since the mirror only holds posts a scan already accepted past its activation
boundary. Each restored post's extraction is looked up in `post_extractions`
and reused when its fingerprint still matches. Missing or outdated extraction
caches may require OCR again. Restore is best-effort: if the mirror is
unavailable, the run has only its local archive and logs the reduced coverage.

Posts outside the discovery overlap are re-fetched by shortcode only while the
event they support has not ended; after that a club's edits cannot change a
listing that is already over. Those requests are deduplicated against whatever
discovery already fetched this run. Requests stay sequential under Instaloader's
rate controller — the optimization here is avoiding repeated collection, OCR and
model work, not fetching harder.

### First-slide extraction

`extract_posts.py` downloads and reads **only the first slide of each post**,
plus its caption, and caches the image result under a
signature-free media key derived from the CDN path. The extraction fingerprint
covers the caption, publication context, first-slide media identity, and
`EXTRACTION_VERSION` — deliberately not the signed URL, which Instagram rotates
on every fetch:

* An unchanged rerun makes **zero** OCR and model calls.
* A refreshed CDN URL alone changes nothing and costs nothing.
* A caption edit expires the assessment but reuses the first image's OCR.
* Replacing the first slide reads its new image; changes to later slides do not
  trigger downloads, OCR, or reassessment.
* Older full-carousel extractions are rebuilt using only the first slide,
  reusing its cached OCR and QR results when available.

A failed image download or an incomplete OCR is a **retryable error**, never a
negative decision. A missing or failed first image does not fall back to later
slides. If the first slide is a video, Instagram's cover JPEG is read. Carousel
length no longer causes a skip: even a 20-slide carousel reads only slide one.

Only the first slide is stored as the flyer. Event details or QR codes that
appear exclusively on later slides are not read.

### Publication

Post sources are assessed by the same `content_assessment` validator as every
other source, under a namespaced key `instagram:post:<media_id>` with
`origin="instagram"` and the existing public event shape. The caption and each
slide's OCR are separate `texts` fields (`caption`, `slide_1_ocr`,
`slide_2_ocr`, …), so activity, date, and location evidence stays attributable
to the slide that actually printed it. Caption-only evidence is allowed — a
post with blank images can still announce an event.

`make_update` publishes assessed Instagram posts. Posts use `instagram_rows.py` for event IDs, host privacy, stale-at-posting
checks, midnight repair, classification, free-food detection, and RSVP handling.
Caption and OCR text both inform repairs and fallback categories; free food
remains a separate `has_free_food` flag. Occurrences and schedules cite named
locations in `location_evidence`, which also participates in carousel flyer
selection. Assessment version 3 refreshes semantic decisions using saved text.

**A post publishes exactly one occurrence.** A carousel holding a whole term's
schedule cannot be turned into one listing without choosing a session on the
reader's behalf, so multiple occurrences and recurring schedules are skipped
with an explicit reason.

Each post publishes its durable `/p/` permalink. Two unrelated clubs announcing
the same title at the same time keep separate listings.

Event IDs use `ig_<owner>_p<media_id>`: distinct posts never overwrite each other
just because their deadlines match, and caption or date corrections retain the
post's ID. Repeat advertisements still pass through semantic reconciliation.
On republication, the registry retires unsupported legacy owner/time IDs and
preserves their admin locks and tombstones; no assessment refresh is needed.

Everything downstream is unchanged: caption corrections may replace or withdraw
that post's support while another valid source keeps the event alive, errors
retain prior support, and admin locks and tombstones remain authoritative
inside the publication RPC.

A post edited until it says nothing withdraws its listing the same way. Once a
post has published a row, a `no_text` extraction — no caption and no printed
text anywhere — publishes a complete assessment with no rows, so deleting a
caption retires the listing exactly as replacing it with words that announce
nothing does. Nothing is left to assess, so the withdrawal costs no model call.
What a post *cannot be read* for is the opposite case and retains its support:
`unsupported_media` is a limit of this reader and `no_media` a defect in the
archived record, and neither says anything about the event.

Apply `supabase/migrations/20260913000000_instagram_posts.sql` before the first
post run. It adds `instagram_posts`, `post_extractions`, and
`instagram_post_checkpoints` plus the `claim_post_activation` RPC. No change to
`source_assessments` or `reconcile_source_assessments` is needed — posts reuse
both.

### Rolling it out

Collection and extraction report as separate pipeline stages
(`instagram.posts.scrape`, `instagram.posts.extract`, `instagram.publish`), so
a failure is attributable and archived posts are still processed after a
collection failure. Counters for discovered, refreshed, unchanged, skipped,
failed, OCR calls, cache hits, and stage duration land in the run summary and
`data/run_history.jsonl`. The daily schedule is unchanged.

Run a pilot on a few real accounts with publication and notifications disabled
before enabling post publication, and inspect the source evidence and generated
rows first:

```bash
# Collect only these accounts, and activate only these accounts.
python scrape_posts.py --handle acm_ucr --handle ieeeucr

# OCR + assess them, publishing nothing and notifying nobody. The report holds
# the source evidence and the event rows that *would* have been written.
python extract_posts.py --handle acm_ucr --handle ieeeucr \
  --dry-run --report /tmp/post-pilot.json

# Re-inspect one source after a fix, still without publishing.
python assessed_events.py --source instagram:post:<media_id> --report /tmp/post.json

# Retry a named failed assessment even if it never produced a listing.
# Uses saved caption/OCR, refreshes only failures, and defaults to no publication.
# Repeat --source to select more failures; --apply publishes without notifications.
# A retry preview writes its report only; it leaves the failed cache selectable.
python assessed_events.py --retry-failed --source instagram:post:<media_id> \
  --report /tmp/retry-post.json
```

New assessments cite source fields; original text is attached by the pipeline,
so emoji, accents, bullets and OCR line breaks are not rewritten by the model.
Refused assessments retain both responses and validation errors in
`validation_attempts`. Existing decisions stay cached until text changes or an
explicit refresh/retry is requested. Gemini transport calls have one attempt and a 60-second timeout. A transport or
quota failure ends assessment for this run; completed updates are still published.
A content validation rejection is recorded per post and does not stop other posts.

Read `/tmp/post-pilot.json` before enabling publication: each entry carries the
assessment's quoted evidence next to the row it produced, so a wrong date or an
invented activity is visible without querying the database. When it looks right,
drop `--dry-run` (keep `--no-notify` for the first real run), then confirm the
listings in the running site — flyer, permalink, date, host, and duplicate handling.

Performance and collection reliability have to be measured in that pilot; the
architecture alone does not establish them.

For a bounded trial of direct post fetching, use:

```bash
python scrape_posts.py --direct-feed --handle acm_ucr --handle ieeeucr
```

This opt-in path uses the stored Instagram IDs with
`/api/v1/feed/user/<user_id>/`, following the
[upstream endpoint workaround](https://github.com/instaloader/instaloader/issues/2689).
It accepts 1–5 explicitly named roster accounts and attempts at most three feed
pages per account (12 requested items per page). It skips the separate refresh
pass. Scheduled runs use the GraphQL iterator described above.

Requests use the live Instaloader session and rate controller, retaining request
pacing, response diagnostics, session-cookie rotation, account jitter, and the
persisted collection cooldown. Each direct page gets one attempt; a throttle or
challenge stops collection without retrying or switching endpoints. Logs report
attempted feed pages and elapsed time per account. These page counts exclude
roster discovery and any additional media-metadata requests Instaloader needs.
Both paths skip the profile-metadata query; endpoint throttling still determines
whether switching to the v1 endpoint improves elapsed time.

Activation, overlap, pinned-prefix handling, and durable writes apply as usual.
If the page budget ends before the date boundary or feed exhaustion, collected
records are mirrored but `scanned_through` stays unchanged and the command exits
with an incomplete-coverage error. Missing page fields or pagination cursors
also retain progress. To finish coverage, rerun those handles without
`--direct-feed` after any cooldown expires; repeatedly running the bounded pilot
on a busy account may only revisit the same newest pages. Collection writes raw
posts and checkpoints; it does not publish events or send notifications.

Out of scope for the direct-feed pilot: historical backfill, comments, profile-link
crawling, and any schedule change. A missing post or a failed
fetch never proves an event was cancelled.

## A note on Instagram's TOS

Scraping IG violates their terms of service. This is fine for a campus
project pulling public-ish content from accounts you'd otherwise see by
following them, but don't redistribute media, don't hammer the API, and
expect the account you log in with to occasionally get checkpointed. For
anything production-grade, talk to clubs about an opt-in Instagram feed
instead of relying on scraping forever.

### Following-feed discovery (opt-in)

The default remains `profiles`. The new `following` mode reads the chronological
Following timeline once for the configured roster, then reconciles a rotating
batch of profiles. It uses the existing saved Instagram session in a temporary
headless Chromium context; it does not require a separate browser login/profile.

Install the optional browser dependency from `pipeline/`:

```bash
.venv/bin/python -m pip install -r requirements-following.txt
.venv/bin/python -m playwright install chromium
```

Run a bounded pilot using exact handles from the roster:

```bash
.venv/bin/python scrape_posts.py --discovery following --handle acm_ucr --following-max-pages 10
```

`--handle` filters archived posts and profile checks. The browser still traverses
the shared Following timeline; Instagram has no timeline filter for those handles.
Account activation stays forward-only, so newly activated clubs do not backfill.

For the complete roster:

```bash
.venv/bin/python scrape_posts.py --discovery following --reconcile-accounts 120
```

After comparing coverage, set `PIPELINE_POST_DISCOVERY=following` in `pipeline/.env`
to use it through `run.py`/the daily runner. Revert to `profiles`, or use
`--discovery profiles`, for a full profile scan. `--direct-feed` remains a separate
profile-only pilot. Hosted runners need the optional dependency and Chromium too;
the existing workflow continues to use profile mode by default.

How it works and how to assess it:

- The browser opens `/?variant=following` and captures a GraphQL request whose
  variables explicitly select `pagination_source=following`. The collector
  replays that observed query from the first page, keeping its current query ID.
  This includes posts preloaded in the initial HTML without parsing that HTML.
  A URL alone is insufficient proof of Following mode; an unrecognized request
  or response fails without moving feed progress.
- Captions, carousel images, video covers, authors and accepted collaborators are
  normalized directly into the existing archive. No per-post metadata query is
  needed. Ads and nested recommendations are excluded; media IDs deduplicate
  repeated entries.
- `data/following_checkpoint.json` is separate from profile `scanned_through`.
  Feed progress moves only after durable page writes and either timeline
  exhaustion or two consecutive pages older than the overlap, provided the
  observed timeline stayed chronological. One old/already-seen post never stops
  a scan. Out-of-order results require walking to exhaustion. The default budget
  is 100 pages; a timeout, malformed cursor, or exhausted budget retains progress.
  Missing state or a changed login/roster/activation reuses profile boundaries.
- Following mode uses the saved roster (`data/followed_accounts.json` for the
  default account source), avoiding a follow-list traversal on every run. Refresh
  that roster with a normal profile run when subscriptions change. All roster
  accounts need stored numeric IDs. Accounts not actually followed by this login
  depend on profile reconciliation.
- The oldest-attempted 120 profiles are reconciled per run, including previously
  unreadable accounts in the rotation. For 800 accounts this takes seven runs;
  at one run/day, a feed omission could therefore take about a week to recover.
  Raise `--reconcile-accounts` for a shorter recovery interval. Existing profile
  checkpoints advance only after their own completed durable scans.
- Logs include feed pages/posts/time and `Following comparison` entries showing
  profile posts absent from the feed in the interval it traversed. Compare several
  runs before relying on the speedup; posts published after the feed run started
  are excluded from this comparison. These are sampled comparisons, not proof of
  complete recall. Use a full profile scan when comprehensive coverage is needed.
- Posts backing upcoming events still receive the existing edit-refresh pass.
  A normal feed failure permits only the bounded reconciliation batch and makes
  the run fail visibly. Throttling/challenges stop collection immediately and use
  the existing shared cooldown; there is no profile fallback after pushback.

This private web interface can change. Offline tests validate the recovery and
normalization rules; only an authenticated run can validate the current interface
for your account, and multiple comparison runs are needed to measure recall.
