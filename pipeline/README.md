# UCR data pipeline

Three sources right now, hand-off to the Next.js app via Supabase tables:

| Source | Scraper | Raw | Table | App reader |
| --- | --- | --- | --- | --- |
| Instagram stories | `scrape.py` ([instaloader](https://github.com/instaloader/instaloader)) + `extract_stories.py` | `data/raw/<handle>/` | `stories`, `events` | `src/lib/events/index.ts` |
| events.ucr.edu (Localist) | `ucr_events.py` (JSON API) | `data/raw/ucr_events/` | `events` | `src/lib/events/index.ts` |
| highlanderlink.ucr.edu (CampusLabs Engage) | `highlander_link.py` (JSON API) | `data/raw/highlander_link/` | `events` | `src/lib/events/index.ts` |

`run.py` scrapes everything, extracts IG event rows, then normalizes. Failures
in one source don't kill the others. IG raw files are the durable story archive;
Localist and HighlanderLink raw files are the latest successful source snapshot.

Stories expire from Instagram after 24 hours, so the IG raw archive is the
only durable record — keep it. Localist and HighlanderLink events are mutable
(descriptions get edited or events disappear), so those scrapers overwrite
current files and prune files absent from a completed source fetch.

## Layout

```
pipeline/
├── accounts.json          # IG handles to monitor (edit me)
├── config.py              # paths + env-driven auth config
├── scrape.py              # IG ingest:        data/raw/<handle>/<story_id>.json
├── extract_stories.py     # IG OCR + LLM:     data/extracted/<story_id>.json
├── ucr_events.py          # Localist ingest:  data/raw/ucr_events/<event_id>.json
├── highlander_link.py     # Engage ingest:    data/raw/highlander_link/<event_id>.json
├── normalize.py           # IG raw stories -> Supabase stories
├── normalize_events.py    # Localist + HighlanderLink events -> Supabase events
├── run.py                 # scrape all + extract + normalize all
├── requirements.txt
├── data/raw/              # gitignored; per-item JSON
├── data/extracted/        # gitignored; per-story extraction cache
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
session is fine for per-account story fetch — the follow-list GraphQL call is
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
get throttled. `scrape.py` already sleeps 2–5s between accounts.

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
python scrape.py             # IG ingest only
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

## Configurable event recognition

[`classification_rules.json`](classification_rules.json) contains the recognition
policy previously embedded in `classify.py`. The engine applies this metadata to
normalized event fields from the existing source parsers. It determines student
relevance, `content_kind`, and free-food signals. Source fetching, OCR, date/location
extraction, and the separate topic `category` mapping remain in their existing stages.

The file has a schema `version` (currently `1`), two ordered rule sets
(`student_relevance` and `content_kind`), a `free_food` condition, and regression
`examples`. Each rule has:

| Metadata | Meaning |
| --- | --- |
| `id` | Stable name returned in explanations; unique within its rule set. |
| `description` | Optional explanation of the format and why it matches. |
| `when` | Conditions on event fields, optionally combined with `all`, `any`, or `not`. |
| `value` | Boolean for student relevance; an existing content kind for classification. |
| Position in `rules` | Priority: first matching rule wins, otherwise the rule set's `default`. |

A field condition has `field`, `match`, and a non-empty `patterns` list. A match
against **any** listed pattern succeeds. Supported fields are `origin`, `title`,
`description`, `tags`, `audiences`, and `text`. Collections match each value
independently. `text` combines the title, description, tags, and audiences, with
case folding as in the previous classifier. Origin is kept separate for source
scoping.

- `contains`: case-insensitive substring matching, preserving the existing keyword behavior.
- `equals`: exact, case-sensitive matching (useful for source identifiers and tags).
- `regex`: case-insensitive Python regular-expression search. In JSON, escape
  backslashes: `"\\bdeadline\\b"` matches whole words.
- `{"all": [...]}`, `{"any": [...]}`, `{"not": {...}}`: compose or exclude conditions.
- `{"student_relevant": true}`: reference the completed relevance decision inside
  a `content_kind` rule. It is unavailable in relevance/food rules, so rules cannot
  reference themselves.

Student relevance is evaluated first. The shipped order preserves source defaults,
student audiences, non-student audience restrictions, and explicit eligibility text.
Content-kind rules then preserve fundraiser → student deadline → student event
precedence, with `other` as the fallback. `free_food` is a separate condition over
`text`, because existing callers pass it text blobs rather than event objects.

### Teaching a new pattern through metadata

For example, if a new Localist title says **“RSVPs shut on September 10”**, add this
rule to `content_kind.rules` after `fundraiser` and before `student-event`:

```json
{
  "id": "rsvp-cutoff-format",
  "description": "A new Localist title format denotes a student cutoff.",
  "when": {
    "all": [
      {"student_relevant": true},
      {"field": "origin", "match": "equals", "patterns": ["localist"]},
      {"field": "title", "match": "regex", "patterns": ["\\brsvps? shut on\\b"]},
      {"not": {"field": "title", "match": "contains", "patterns": ["preview"]}}
    ]
  },
  "value": "student_deadline"
}
```

Add the event and expected result to `examples` in the **same config file**:

```json
{
  "name": "New RSVP cutoff",
  "event": {
    "origin": "localist",
    "title": "RSVPs shut on September 10",
    "audiences": ["Students"]
  },
  "expected": {"content_kind": "student_deadline", "rule_id": "rsvp-cutoff-format"}
}
```

Include nearby negative examples too: a staff-only audience should remain `other`,
and cutoff language appearing only in the description should remain an event.
For new student eligibility language, append a relevance rule after the existing
audience rules so explicit restrictions retain priority.

Validate the metadata and all its regression examples from the repository root:

```bash
python pipeline/classify.py --check
python -m unittest discover -s pipeline/tests -p 'test_*.py' -v
```

To inspect one case, save the normalized `event` object to a JSON file, then run:

```bash
python pipeline/classify.py --event /tmp/event.json
```

The output includes `content_kind`, `rule_id`, `student_relevant`, and
`student_rule_id`. A null rule ID means that stage used its configured fallback;
for example, a restricted audience can explain an `other` result. These commands
run locally without fetching events or updating Supabase. `--check` exits nonzero
for invalid rules or failed examples; CI also runs the shipped config examples.

The pipeline loads and compiles the configuration once per process. The next run
picks up edits; restart any long-lived process after changing rules. To try a
separate full configuration, use `--rules /path/to/rules.json` for the CLI or
`PIPELINE_CLASSIFICATION_RULES=/path/to/rules.json` for pipeline callers. The default
path is relative to the engine file, independent of the working directory. Invalid
configuration reports its location and fails rather than silently using defaults.

New recognition patterns over these fields require metadata and example changes
only. The four output kinds (`student_event`, `student_deadline`, `fundraiser`,
`other`) remain the database/app contract; introducing a new stored kind or a new
source field requires the corresponding schema/source integration work.

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
the database for diagnostics but is not replayed as a cache hit.

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

## A note on Instagram's TOS

Scraping IG violates their terms of service. This is fine for a campus
project pulling public-ish content from accounts you'd otherwise see by
following them, but don't redistribute media, don't hammer the API, and
expect the account you log in with to occasionally get checkpointed. For
anything production-grade, talk to clubs about an opt-in feed (e.g. they
post to a shared Highlander Link or our own submission form) instead of
relying on scraping forever.
