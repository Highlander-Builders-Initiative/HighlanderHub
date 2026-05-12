# Instagram stories pipeline

Pulls stories from a configured list of UCR-adjacent Instagram accounts using
[instaloader](https://github.com/instaloader/instaloader), persists them to a
durable raw archive, and emits a single `output/stories.json` for the Next.js
app to read.

Stories expire from Instagram after 24 hours, so the raw archive in
`data/raw/` is the only durable record — keep it.

## Layout

```
pipeline/
├── accounts.json          # handles to monitor (edit me)
├── config.py              # paths + env-driven auth config
├── scrape.py              # ingest:    IG → data/raw/<handle>/<story_id>.json
├── normalize.py           # transform: data/raw/** → output/stories.json
├── run.py                 # scrape + normalize in one shot
├── requirements.txt
├── data/raw/              # gitignored; per-story JSON, idempotent
└── output/stories.json    # gitignored; consumed by src/lib/scrapers/instagram.ts
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

**Option B — username + password env vars (interactive 2FA):**

```bash
export IG_USERNAME=your_ig_username
export IG_PASSWORD=...
```

Use a **dedicated account**, not your personal one. Instagram is aggressive
about flagging accounts that look like scrapers — expect occasional
checkpoints / temporary blocks, and add jitter / lower the cadence if you
get throttled. `scrape.py` already sleeps 2–5s between accounts.

## Run it

```bash
python run.py                # scrape + normalize
python scrape.py             # ingest only
python normalize.py          # rebuild output/stories.json from raw/
```

Re-running is cheap: existing raw files are skipped. Normalize is a pure
function of `data/raw/`.

## Schedule

Stories live 24h, so 4–6× a day is a reasonable cadence. Sample crontab:

```
0 */4 * * * cd /path/to/HighlanderHub/pipeline && .venv/bin/python run.py >> pipeline.log 2>&1
```

## Output schema

`output/stories.json`:

```jsonc
{
  "generatedAt": "2026-05-11T20:00:00+00:00",
  "count": 42,
  "stories": [
    {
      "id": "3140000000000000000",        // IG mediaid (stable)
      "handle": "acm.ucr",
      "account_label": "ACM at UCR",
      "account_category": "club",
      "owner_userid": 123456,
      "owner_username": "acm.ucr",
      "typename": "GraphStoryImage",      // or GraphStoryVideo
      "is_video": false,
      "posted_at": "2026-05-11T18:30:00+00:00Z",
      "expires_at": "2026-05-12T18:30:00+00:00Z",
      "image_url": "https://scontent...jpg",
      "video_url": null,
      "caption": null,                    // stories rarely have captions
      "caption_mentions": ["other.handle"],
      "story_cta_url": "https://lu.ma/..." // link sticker if any
    }
  ]
}
```

## Hand-off to the app

The Next.js app reads this file via `src/lib/scrapers/instagram.ts`. That
module is a best-effort adapter: a story with no caption, no link sticker,
and no OCR is just an image + a posting time, which is not enough to fill
out a `CampusEvent`. Stories whose CTA URL points at a known event host
(lu.ma, eventbrite, highlanderlink.ucr.edu) become events directly;
everything else is exposed as raw "story" items the UI can show separately.

## Next step: extraction

The interesting work — turning a story image into a structured event — is
not in this pipeline yet. The clean seam is a separate `extract.py` that
reads `data/raw/**` and writes `data/extracted/<id>.json` with
`{title, startsAt, location, ...}`. Reasonable approaches:

- **OCR**: `pytesseract` on the image, regex out dates / times / locations.
  Cheap, brittle, decent baseline.
- **Vision LLM**: send the image + a small prompt to Claude (or similar)
  asking for a `CampusEvent` JSON. Slower, costs money, much more accurate
  on the kinds of flyer-style stories clubs actually post.

Either way: keep extraction idempotent per-id, and let normalize.py merge
the extracted layer in.

## A note on Instagram's TOS

Scraping IG violates their terms of service. This is fine for a campus
project pulling public-ish content from accounts you'd otherwise see by
following them, but don't redistribute media, don't hammer the API, and
expect the account you log in with to occasionally get checkpointed. For
anything production-grade, talk to clubs about an opt-in feed (e.g. they
post to a shared Highlander Link or our own submission form) instead of
relying on scraping forever.
