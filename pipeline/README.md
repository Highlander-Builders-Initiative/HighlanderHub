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
much more slowly — once a day is plenty, but since `run.py` does both, the
IG cadence drives the schedule.

```
0 */4 * * * cd /path/to/HighlanderHub/pipeline && .venv/bin/python run.py >> pipeline.log 2>&1
```

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
