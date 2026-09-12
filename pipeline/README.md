# UCR data pipeline

Three sources right now, hand-off to the Next.js app via Supabase tables:

| Source | Scraper | Raw | Table | App reader |
| --- | --- | --- | --- | --- |
| Instagram stories | `scrape.py` ([instaloader](https://github.com/instaloader/instaloader)) + `extract_stories.py` | `data/raw/<handle>/` | `stories`, `events` | `src/lib/events/index.ts` |
| Instagram posts | `scrape_posts.py` + `extract_posts.py` | `data/posts/<handle>/` | `events` | `src/lib/events/index.ts` |
| events.ucr.edu (Localist) | `ucr_events.py` (JSON API) | `data/raw/ucr_events/` | `events` | `src/lib/events/index.ts` |
| highlanderlink.ucr.edu (CampusLabs Engage) | `highlander_link.py` (JSON API) | `data/raw/highlander_link/` | `events` | `src/lib/events/index.ts` |

Instagram posts are a second channel over the same account list and the same
daily run. They are collected forward-only from each account's activation
timestamp, publish through the same assessment/reconciliation boundary as
stories, and never enter the frontend's `stories` table.

`run.py` scrapes everything, extracts IG event rows, normalizes, then reconciles
corroborated duplicates across sources. Its seventh stage prefers structured
campus metadata while retaining a missing end date or RSVP link from a matching
flyer. Matches require the same start instant plus a distinctive title and
compatible host/location, or a shared registration link and related title.
Generic meetings from different clubs stay separate. Locked rows win and
deleted source identities suppress their duplicate group. Notifications run
only after reconciliation in the combined runner. Failures
in one source don't kill the others. IG raw files are the durable story archive;
Localist and HighlanderLink raw files are the latest successful source snapshot.

Stories expire from Instagram after 24 hours, so the IG raw archive is the
only durable record — keep it. Localist and HighlanderLink events are mutable
(descriptions get edited or events disappear), so those scrapers overwrite
current files and prune files absent from a completed source fetch.

Recurring Localist series run by UCR Recreation with at least three instances
contribute only their next ongoing/upcoming session. Other recurring events
still expand into separate occurrences. The source link preserves access to
the full recreation schedule; each successful run advances the selected
session and reconciles old unlocked occurrence rows.

## Layout

```
pipeline/
├── accounts.json          # IG handles to monitor (edit me)
├── resolve_ids.py         # fills instagram_user_id for handles added by hand
├── config.py              # paths + env-driven auth config
├── scrape.py              # IG stories:       data/raw/<handle>/<story_id>.json
├── extract_stories.py     # IG OCR + LLM:     data/extracted/<story_id>.json
├── scrape_posts.py        # IG posts:         data/posts/<handle>/<media_id>.json
├── post_archive.py        # post archive I/O, free of Instaloader
├── extract_posts.py       # per-slide OCR:    data/post_extractions/<media_id>.json
├── story_dates.py         # what the flyer text says about day and time
├── ucr_events.py          # Localist ingest:  data/raw/ucr_events/<event_id>.json
├── highlander_link.py     # Engage ingest:    data/raw/highlander_link/<event_id>.json
├── normalize.py           # IG raw stories -> Supabase stories
├── normalize_events.py    # Localist + HighlanderLink events -> Supabase events
├── run.py                 # scrape all + extract + normalize all
├── requirements.txt
├── data/raw/              # gitignored; per-item JSON
├── data/extracted/        # gitignored; per-story extraction cache
├── data/posts/            # gitignored; per-post record
├── data/post_extractions/ # gitignored; per-post slide OCR cache
├── data/post_checkpoints.json  # gitignored; activation + scan progress
└── output/                # gitignored; legacy local dumps
```

## Setup

```bash
cd pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Auth

Instagram requires a logged-in session to fetch stories. Pick one:

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
session is fine for the story fetch — the follow-list GraphQL call is
what failed. The scraper falls back to `data/followed_accounts.json`, then
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
get throttled. `scrape.py` asks about 50 accounts per request and sleeps
5–15s between requests, so a full run is ~17 story requests rather than one
per account.

## Editing accounts.json

`scrape.py` asks Instagram for stories by numeric user id, not by handle, so
every entry needs an `instagram_user_id`. Handles added by hand (or by
`discover.py`) don't have one:

```bash
python resolve_ids.py          # fills in every account missing an id
python resolve_ids.py --dry-run
```

Accounts still missing an id are skipped by the scrape and named in a warning —
they are invisible to the run until resolved.

Supabase writes and story extraction also need credentials in `pipeline/.env`:

```bash
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
DISCORD_WEBHOOK_URL=...
GOOGLE_VISION_API_KEY=...
GOOGLE_CLOUD_PROJECT=...
GOOGLE_CLOUD_LOCATION=global
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

## Run it

```bash
python run.py                # scrape all sources + extract + normalize all
python scrape.py             # IG story ingest only
python scrape_posts.py       # IG post ingest only (--handle to limit a pilot)
python extract_posts.py      # per-slide OCR + publish (--dry-run to inspect first)
python extract_stories.py    # OCR + Gemini extraction from existing IG raw files
python ucr_events.py         # UCR events ingest only (no auth needed)
python highlander_link.py    # HighlanderLink ingest only (no auth needed)
python normalize.py          # rebuild Supabase stories from data/raw/
python normalize_events.py   # rebuild events from ucr_events/ + highlander_link/
```

Re-running is cheap: IG raw files are skipped if present, extracted story
results are cached first in `data/extracted/` and then in Supabase
`story_extractions` for stateless CI runs, and Localist + HighlanderLink events
are overwritten/pruned because they are mutable.

A cached `ok` extraction records Gemini's response, not verified event quality.
`story_dates.py` owns every question of the form "what day and time does the
source text support?", with one date vocabulary and two policies over it: the
narrow `override_dates` the wall-time override can rebuild a timestamp from,
and the broad `evidence_dates` that only has to prove a day was printed.
Instagram event mapping requires date evidence in OCR or the story caption;
posting timestamps, model descriptions, tags, and confidence cannot supply it.
A printed calendar date stands on its own. Immediacy words bind the event to
`posted_at` instead of unlocking the model's clock: `now`/`rn` take the posting
instant, `today`/`tonight`/`tomorrow` fix the day and leave the time to
extraction, and a printed date outranks all of them. Calls to action (`apply
now`, `applications are now open`, `book your appointment now`) are not
immediacy claims. Bare weekdays and bare `M/D` are too easy to read out of
prose and room numbers, so they need a corroborating neighbour: a clock time on
the flyer, a second slash date across a range dash (`recruitment is
10/8-10/11`), or — for `M/D` — a weekday printed beside it (`signups close
Thursday (6/11)`).

The weekday and date must form one expression; a nearby greeting or a fraction
such as `1/2 price` does not qualify. `Apply today` is also a call to action,
not evidence of an event happening today. Explicit evening-to-midnight ranges
such as `September 19, 2026 5PM–12AM` end at midnight on the following day.

Multi-day grids and weekday practice schedules are skipped when one event
cannot represent the flyer. A clear `today` reminder for a single session can
still use a reused schedule flyer. Skipped schedules and corrected timestamps
retire their old row IDs, including IDs previously derived from posting time;
admin locks/deletions continue to apply to replacement identities.

Reshares use the original author when known, otherwise the attached post's
`media_id`. Copies of the same post share observed author metadata during
mapping, so missing OCR bylines do not create one event per resharing club.

RSVP mapping rejects Instagram destinations and bare shortener homepages.
Spaces inside a short link are removed only when the full spaced link is
corroborated by an OCR line. QR codes are decoded locally from flyer images;
their destinations are never fetched by the decoder. A valid story CTA wins,
then a single QR destination, then the extracted URL. Multiple distinct QR
destinations remain ambiguous. `rsvp_required` stays true when no usable link
can be recovered.

Upcoming cached RSVP flyers receive one QR scan without repeating OCR/Gemini.
The scan version and destinations are stored inside the existing result JSON
for both local and remote caches, including successful scans with no QR code.
Download/decoder failures remain retryable. Install the updated requirements
before running extraction. Content-kind mapping reads OCR for appointment and
application signals, but limited capacity alone never makes an event an
application. Text-only backfills skip Instagram unless explicitly requested.

Undated posts are skipped even from existing caches, and their prior event IDs
enter the existing unlocked-row cleanup unless another accepted story supports
the same ID. This is not full semantic verification; unrecognized date
expressions are conservatively skipped. A single printed calendar day now
corrects the model's day even without a time range. An unrelated model day on
a multi-date flyer is rejected. Corroborated dotted dates (`10.31` beside a
clock) and separate numeric tiles explicitly labeled `MONTH DAY YEAR` are
recognized; bare prices and room numbers remain excluded. Date-only month/day
ranges include the entire last day. Awareness/resource posts and service
closures are not student gatherings.

## Schedule

Stories live 24h, so 4–6× a day is a reasonable cadence. UCR events change
much more slowly — once a day is plenty. The supported unattended runner is
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
locally because the run comes from a residential IP and `scrape.py` writes the
rotated `sessionid` back to `IG_SESSION_FILE` after every run. On a CI runner
that file is ephemeral, so each run replays the same increasingly stale cookie
from `IG_SESSION_FILE_B64` until Instagram rejects it — which is why the cron
in `.github/workflows/scrape.yml` is commented out.

Scheduling cannot renew an expired session. When the Instagram step starts
failing with `400 ... "invalid request"`, quit Safari and re-run
`import_safari_session.py`.

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
  "id": "ig_cyber_ucr_3894795737410658765",
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
  "source_url": "https://www.instagram.com/stories/cyber_ucr/3894795737410658765/",
  "image_url": "https://...supabase.co/storage/v1/object/public/event-flyers/instagram/cyber_ucr/3894795737410658765.jpg",
  "is_free": true,
  "rsvp_required": true,
  "rsvp_url": "https://lu.ma/...",
  "scraped_at": "2026-05-14T12:00:00+00:00"
}
```

### `stories`

```jsonc
{
  "id": "3140000000000000000",
  "handle": "acm.ucr",
  "account_label": "ACM at UCR",
  "account_category": "club",
  "owner_userid": 123456,
  "owner_username": "acm.ucr",
  "typename": "GraphStoryImage",
  "is_video": false,
  "posted_at": "2026-05-11T18:30:00+00:00Z",
  "expires_at": "2026-05-12T18:30:00+00:00Z",
  "image_url": "https://scontent...jpg",
  "video_url": null,
  "caption": null,
  "caption_mentions": ["other.handle"],
  "story_cta_url": "https://lu.ma/...",
  "permalink": "https://www.instagram.com/stories/acm.ucr/3140000000000000000/"
}
```

## Hand-off to the app

The Next.js app reads upcoming events from the Supabase `events` table via
`src/lib/events/index.ts`. `extract_stories.py` writes Instagram flyers into that
same table with `source='instagram'`, so extracted IG events appear alongside
Localist events without a frontend change.

If `DISCORD_WEBHOOK_URL` is set, the pipeline posts newly discovered free-food
events to Discord after Supabase upsert. The `discord_notifications` table
records successful sends by a durable `notification_key` based on the public
event identity, so reruns and generated row ID changes do not repost the same
event.

## Instagram story extraction

Imported content now passes through `content_assessment.py` before publication.
Instagram OCR/captions and structured campus listings use the same typed decision:
activity, deadline, application, service schedule, announcement, or uncertain.
The decision records the role of its dates and exact source evidence. Awareness
observances are announcements; real workshops or vigils during a campaign remain
activities. All-day and multi-day activities remain supported. Explicit bounded
recurring hours become individual sessions, with printed breaks respected. A
timed occurrence may not exceed 24 hours, so seasonal hours and daily visiting
hours cannot publish as one continuous weeks-long span.

`assessed_events.py` applies student eligibility and fundraising policy separately,
then publishes student events/deadlines. Nonpublic decisions remain inspectable
in `source_assessments`, alongside source text, evidence, reasons, version, model,
and the IDs each source supports. The last successful assessment is retained
after a failed reassessment. The frontend's existing end-time visibility policy
continues to keep real ongoing events visible.

Apply `supabase/migrations/20260911000000_source_assessments.sql` before running
the new importers. Its service-role-only RPC atomically updates source ownership,
saves current rows, and removes obsolete imported rows only when no other source
supports them. Admin locks and deleted identities constrain replacements. An
assessment/API error preserves prior support and causes the stage to report a
retryable failure. A successful `uncertain` decision stays unpublished.

Semantic caches live in `data/assessments/` and the database. Changing the source
text, assessment version, or model invalidates them without repeating OCR or
image downloads. Bump `content_assessment.VERSION` when changing assessment
semantics or the prompt after deployment. Source reviews recorded with
`record_review` retain reviewer attribution and still expire on source/policy
changes. Old `is_event` cache values are extraction hints, not publication gates.

Reassess existing saved evidence (dry run by default, no notifications):

```bash
python assessed_events.py --active --report /tmp/assessment-report.json
python assessed_events.py --source instagram:3977797394086504274 --report /tmp/one-source.json
python assessed_events.py --active --apply
```

The initial migration of an existing feed should assess all sources supporting
the affected event group together so legacy duplicates acquire ownership before
cleanup. `--active` includes sources identifiable through legacy IDs or stored
source URLs. Review the report before applying; failures are distinct from
intentional exclusions. The command reads saved source text and may call the
configured Gemini service, but never scrapes, downloads media, runs OCR, or sends
Discord notifications.

Verification:

```bash
python -m unittest discover -s tests
python evaluate_content_assessment.py --synthetic --report /tmp/semantic-eval.json
# Include saved-source regressions in a live model evaluation only when authorized:
python evaluate_content_assessment.py --report /tmp/full-semantic-eval.json
```

The root `npm test` also executes the actual publication SQL in disposable
PGlite PostgreSQL, covering rollback, shared support, retries, rekeying, locks,
tombstones, session fanout, and public-role access denial. It also runs both
Python importer entrypoints and applies their actual RPC payloads to PGlite,
checking retirement with a locked sibling. Install `pipeline/requirements.txt`
first; the test uses `pipeline/.venv/bin/python` when present, otherwise `python3`
(or set `PIPELINE_PYTHON`). No network calls are made by these fixtures.
Semantic evaluation uses the real model and is separate from deterministic
contract tests. Explicit occurrences and expanded schedules share a 100-session
limit; oversized schedules fail assessment rather than publishing a partial set.

`extract_stories.py` turns raw IG story image flyers into `events` rows:

1. Walks `data/raw/<handle>/*.json` for handles in `accounts.json`.
2. Skips story IDs already cached in `data/extracted/`; video stories use their
   Instagram cover frame as the flyer image.
3. If the local cache misses, checks Supabase `story_extractions` for a
   terminal result and writes that result back to `data/extracted/`.
4. Downloads `image_url`; expired CDN URLs (`403`, `404`, `410`) are cached
   as `{"status": "image_expired"}`.
5. Sends image bytes to Google Cloud Vision OCR using `GOOGLE_VISION_API_KEY`.
6. If OCR text is empty, caches `{"status": "no_text"}` and skips Gemini.
7. Sends OCR text plus story/account metadata to Gemini 2.5 Flash Lite on
   Vertex AI using Application Default Credentials, `GOOGLE_CLOUD_PROJECT`,
   `GOOGLE_CLOUD_LOCATION=global`, and a JSON response schema. The global
   Vertex endpoint uses `aiplatform.googleapis.com` and bills the configured
   Google Cloud project.
8. If the story is an event, uploads the same downloaded bytes to the public
   `event-flyers` Supabase Storage bucket and caches that durable `image_url`.
9. Caches terminal extraction results in both
   `data/extracted/<story_id>.json` and Supabase `story_extractions`.
10. Upserts cached `status == "ok"` event results into Supabase `events`.

Terminal cache statuses (`image_expired`, `no_text`, `not_event`, `ok`) are
not reprocessed on later runs. Transient download, Vision, Gemini, or remote
cache failures are logged and retried on the next run; `error` is allowed in
the database for diagnostics but is not replayed as a cache hit. Download,
Vision, and Gemini failures persist `result.stage` and `result.error` locally
and remotely. Extraction saves successful items before raising a stage failure
that names unsuccessful story IDs. Direct `run.py` calls also save a rotating
`data/run.log`, so warning details survive a closed terminal.

Run extraction by itself after a scrape:

```bash
python extract_stories.py
```

Expected logs look like:

```text
extract ig_cyber_ucr_3894795737410658765: ok
extract ig_cyber_ucr_3894795737410658766: no_text
Wrote 1 events to Supabase
```

To check the output:

```sql
select id, title, starts_at, host, category
from events
where source = 'instagram'
order by scraped_at desc;
```

## Instagram post collection

Posts are the other half of how a club announces an event, and unlike stories
they do not expire. `scrape_posts.py` walks each account's feed with
Instaloader's `get_posts()`, reading photos and image carousels through
`get_sidecar_nodes()`.

Collection is **forward-only**. Before an account's first fetch the run records
an `activated_at` timestamp, and nothing published before it is ever imported —
including an old post the club pins to the top of its profile later. Activation
is claimed through `claim_post_activation`, which inserts only when absent.
If that claim fails, the local timestamp is retained and retried whenever the
durable row is missing. Progress is mirrored only after the stored activation
matches the scan's boundary. Losing `data/` recovers the durable activation;
if both copies are lost before a claim succeeds, the original boundary cannot
be recovered.

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
and rate limits stop Instagram collection outright, record incomplete coverage, and retain every
checkpoint — continuing would turn one throttle into a run-long pattern of
rejected requests.

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

### Per-slide extraction

`extract_posts.py` reads each image once and caches the result under a
signature-free media key derived from the CDN path. The extraction fingerprint
covers the caption, publication context, ordered media identities, and
`EXTRACTION_VERSION` — deliberately not the signed URL, which Instagram rotates
on every fetch:

* An unchanged rerun makes **zero** OCR and model calls.
* A refreshed CDN URL alone changes nothing and costs nothing.
* A caption edit expires the assessment but reuses every image's OCR.
* A replaced or added slide reads only that slide.
* A carousel repeating one image reads it once.

A failed image download or an incomplete OCR is a **retryable error**, never a
negative decision: the slides that succeeded are kept inside the error payload
and matched by media key on retry, so a partial media failure costs only the
slides that actually failed. Video slides use Instagram's cover JPEG — the same
still stories already OCR as a flyer — so a Reel or a carousel mixing video
with images is read, not skipped. An over-long carousel is skipped as
`unsupported_media` rather than truncated. That status is terminal only while
this version still cannot read the post.

Only slides that can actually be chosen as the flyer are stored durably: the
lead image, and any slide whose text can be cited as evidence.

### Publication

Post sources are assessed by the same `content_assessment` validator as every
other source, under a namespaced key `instagram:post:<media_id>` with
`origin="instagram"` and the existing public event shape. The caption and each
slide's OCR are separate `texts` fields (`caption`, `slide_1_ocr`,
`slide_2_ocr`, …), so activity, date, and location evidence stays attributable
to the slide that actually printed it. Caption-only evidence is allowed — a
post with blank images can still announce an event.

**A post publishes exactly one occurrence.** A carousel holding a whole term's
schedule cannot be turned into one listing without choosing a session on the
reader's behalf, so multiple occurrences and recurring schedules are skipped
with an explicit reason. Stories keep their existing multi-occurrence
behaviour.

A story that reshares a feed post is skipped before download, OCR, or a model
call. The post is collected from the author's grid and is the single source
for that media; re-reading the story embed would duplicate work and a second
`source_assessments` row. Original story flyers (not reshares) are unchanged.

Posts are ordered last in the Instagram publication batch so a listing that
still has both a legacy reshare source and a post keeps the durable `/p/`
permalink rather than a story link that stops resolving within a day. Two
unrelated clubs announcing the same title at the same time still keep
separate listings.

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
python scrape_posts.py --handle acm.ucr --handle ieee.ucr

# OCR + assess them, publishing nothing and notifying nobody. The report holds
# the source evidence and the event rows that *would* have been written.
python extract_posts.py --handle acm.ucr --handle ieee.ucr \
  --dry-run --report /tmp/post-pilot.json

# Re-inspect one source after a fix, still without publishing.
python assessed_events.py --source instagram:post:<media_id> --report /tmp/post.json
```

Read `/tmp/post-pilot.json` before enabling publication: each entry carries the
assessment's quoted evidence next to the row it produced, so a wrong date or an
invented activity is visible without querying the database. When it looks right,
drop `--dry-run` (keep `--no-notify` for the first real run), then confirm the
listings in the running site — flyer, permalink, date, host, and that a post
is not also published as a second card from a story resharing it.

Performance and collection reliability have to be measured in that pilot; the
architecture alone does not establish them.

Out of scope in this version: historical backfill, comments, profile-link
crawling, and any schedule change. A missing post or a failed
fetch never proves an event was cancelled.

## A note on Instagram's TOS

Scraping IG violates their terms of service. This is fine for a campus
project pulling public-ish content from accounts you'd otherwise see by
following them, but don't redistribute media, don't hammer the API, and
expect the account you log in with to occasionally get checkpointed. For
anything production-grade, talk to clubs about an opt-in feed (e.g. they
post to a shared Highlander Link or our own submission form) instead of
relying on scraping forever.
