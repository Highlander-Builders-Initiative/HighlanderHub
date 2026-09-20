# Event ingestion pipeline

`python pipeline/run.py` runs four stages: Apify post collection, first-slide
Google Vision OCR, grounded Gemini event assessment/publication, and event
reconciliation. Publication retains the existing evidence, deduplication,
admin-lock, deletion and notification rules. Failed collection still processes
the saved archive; partial collection permits extraction of newly saved posts.

## GitHub Actions: every eight hours

`.github/workflows/scrape.yml` schedules `0 */8 * * *`: **00:00, 08:00 and 16:00
UTC**, with manual **Run workflow** support. GitHub schedules are best-effort.
The workflow must be on the repository's default branch for cron to run.
Concurrent workflow runs are serialized. Disable any old local launchd/cron
schedule before enabling this workflow against the same database.

Set these repository **Actions secrets**:

| Secret | Purpose |
| --- | --- |
| `APIFY_TOKEN` | Apify API token with access to run the actor and read its dataset |
| `SUPABASE_URL` | Existing project URL |
| `SUPABASE_SERVICE_KEY` | Existing service-role key |
| `GOOGLE_VISION_API_KEY` | First-slide OCR |
| `GEMINI_API_KEY` | Gemini assessment; alternatively use Vertex AI below |

For Vertex AI instead of `GEMINI_API_KEY`, set `GOOGLE_CLOUD_PROJECT` and
`GOOGLE_APPLICATION_CREDENTIALS_B64` (base64 service-account JSON). Credentials
are decoded only when needed. No Instagram account, cookies, browser, password,
`IG_USERNAME` or `IG_SESSION_FILE_B64` is required.

Optional repository **Actions variables**:

| Variable | Default | Meaning |
| --- | --- | --- |
| `APIFY_POSTS_PER_PROFILE` | `100` | Actor export cap per profile, 1–500 |
| `APIFY_MAX_CHARGE_USD` | `10` | Combined charge ceilings for all batches in one collection cycle; excludes Google API costs |
| `APIFY_DISCOVERY_OVERLAP_SECONDS` | `300` | Discovery overlap behind each successful checkpoint (0–3600 seconds) |
| `APIFY_INCOMPLETE_RETRY_HOURS` | `24` | Wait before retrying a profile whose discovery was incomplete (at least 8 hours) |

The actor is [apify/instagram-post-scraper](https://apify.com/apify/instagram-post-scraper),
ID `nH2AHrwxeTRJoN5hX`, pinned to build `0.0.599`. Input is `username`,
`resultsLimit`, `onlyPostsNewerThan` (UTC `Z`, not `+00:00`), `skipPinnedPosts`
and `dataDetailLevel`. A run starts asynchronously, is polled with a 30-minute
actor timeout, and its dataset is read in pages. The token is sent only in an
Authorization header.

Both settings that look optional are load-bearing, and both were measured
against this build rather than taken from its documentation:

- **`skipPinnedPosts: true`.** `onlyPostsNewerThan` on its own still exports —
  and bills for — pinned posts of any age; a 2022 pin came back against a
  three-day window. With both set, pins older than the window are dropped and
  pins inside it are kept, so a club that pins its current flyer is not missed.
- **`dataDetailLevel: "detailedData"`.** `basicData` omits `inputUrl`, which is
  the only field that routes a post back to the requested profile, and omits
  `childPosts`, which carries every carousel slide after the cover. It is
  cheaper per item and unusable.

Coverage is read from the run log, not inferred from the dataset: a profile
advances its checkpoint only when the log acknowledges it by name, in one of
three forms — the cutoff was reached, the feed ran out (`[END-OF-RESULTS]`), or
nothing public sits in the window (`NO RESULTS`). That last form arrives
alongside a `no_items` error record, so an inactive club reports as covered
instead of being retried forever. An unrecognised log contract fails closed and
advances nothing.

The previous actor, `sones/instagram-posts-scraper-lowcost`
(`Y5mzw9TLFReI0d6gQ`), treated its `newerThan` as a pagination hint and exported
whole pages regardless of date: of 5,199 billed items on 2026-09-20, 5,160 were
flagged `is_newer_than_cutoff: false`, reaching back to 2016. Its datasets also
used flattened `image_url` fields and rounded `pk` past 2**53. Both shapes are
still read so already-paid datasets stay ingestible; the composite `id` takes
precedence over `pk` because only it preserves the exact media ID.

## Accounts and incremental collection

Edit `pipeline/accounts.json`; it is now the default roster for collection and
publication. Handles are required; existing numeric Instagram IDs are checked
when present. Accepted coauthors can match the roster, while invited coauthors
and tagged users cannot establish ownership. Public profiles only are supported
by this actor. The old followed-account cache is available only through explicit
`PIPELINE_ACCOUNT_SOURCE=followed`; the scheduled workflow uses `accounts_json`.

Existing Supabase `instagram_post_checkpoints` and `instagram_posts` are reused;
no schema migration is required. A new account activates before its first fetch
and only imports posts from activation onward. Existing accounts keep their
activation and progress, with a five-minute overlap by default. A new deployment therefore
**does not automatically import historical posts**.

The actor's `newerThan` only controls pagination; the adapter also filters each
post's timestamp. Discovery groups accounts whose individual cutoffs fall in the
same UTC hour, using the oldest cutoff within that group. Grouping adds less than
an hour of lookback, and an account stalled weeks ago cannot pull current
accounts back with it. This replaces the former shared seven-day/old-event scan.

**Discovery only: saved posts are never scheduled for rechecks.** Each dataset
is checked against the durable `instagram_posts` media IDs. Already saved IDs
are ignored even if Apify returns a changed caption or image URL. Their original
snapshot is preserved, so incidental duplicates cannot trigger an edit-based OCR
or Gemini rerun. A failed durable ID lookup stops collection before starting a
paid actor rather than treating every post as new.

There is no live-event refresh queue, daily post recheck, or separate request to
renew an expired image URL. New posts still receive first-slide OCR, assessment
and publication. Cached results and unfinished processing can be retried from
saved data; that does not request another scrape of the post. If an image expires
before initial extraction succeeds, this policy can leave that post unprocessed
until explicit maintenance. Missing posts do not imply cancellation.

The event detail flyer already links to the original Instagram post. Visitors
can use that link to check for edits or cancellations. Opening an event does not
trigger an API refresh; HighlanderHub shows the saved event information.

The five-minute overlap is for discovering new posts near the previous boundary,
not for refreshing known posts. A profile with an incomplete scan waits 24 hours
before discovery retries, retaining its previous checkpoint. Healthy profiles
remain eligible every eight hours.

**Zero duplicate Apify charges are not guaranteed.** This actor has no known-post
exclusion list or strict output-date filter. It may return old posts from its
first/boundary pages and charge for those output items even though we ignore
them. A five-minute overlap can miss posts first exposed by Instagram later than
that overlap; increase it if monitoring shows late visibility.

Raw posts are mirrored before local processing. Failed/aborted/timed-out runs,
missing profiles, malformed records, and profiles
hitting the export limit do not advance the affected checkpoints. Saved valid
posts can still be published, but the workflow exits nonzero. An empty profile
is conservatively reported as incomplete because an empty dataset cannot prove
whether the account is empty, private or failed. A nonempty uncapped successful
result relies on the actor's pagination correctness; its public dataset contract
does not expose a complete per-profile coverage certificate.

A cap failure needs investigation or a larger `APIFY_POSTS_PER_PROFILE` (maximum
500); repeating the same capped input cannot recover deeper history. Missing
posts never imply cancellation. The historical maintenance setting
`PIPELINE_POST_BACKFILL_SINCE=YYYY-MM-DD` remains local-only and opt-in; clear it
after maintenance. The scheduled workflow always leaves it blank.

## Failure recovery and costs

`data/apify_plan.json` stores a cycle of discovery batches. Each has its own file under `data/apify_runs/`. Completed batches are
skipped on recovery; unfinished batches resume their existing actor run and
replay its dataset. A consumed dataset is never billed again merely because the
plan update was interrupted. A saved pre-batching `apify_run.json` is finished
once before switching to this planner. If an older saved plan contains refresh
jobs, they are marked skipped without starting, polling or ingesting them.
A refresh actor that was already running externally may still finish and incur
its existing charge; skipping the job does not abort it in Apify.

The total `APIFY_MAX_CHARGE_USD` ceiling is split across the whole plan, **not
multiplied by the number of actors**. All of it is available to discovery,
divided by profile count with at least $0.01 reserved per actor start. Unused ceilings are
not reallocated. A budget too small for all groups fails before any new paid run.
The 30-minute collection time allowance is also shared across the plan; remaining
batches resume next invocation. A successful actor status does not establish
complete coverage if its charge ceiling was reached. Such results are saved but
do not advance collection checkpoints.

Every dataset item is billed at `post` $0.0017 plus `post-details` $0.0010,
and a profile with nothing in its window emits one billable `no_items` record.
A full-roster daily pass is therefore roughly one item per profile — about
$2.30 across ~830 accounts — rising only with the number of real posts found.
Charges settle asynchronously after a run reports SUCCEEDED, so the cost read
back moments after a run finishes can understate the final total.

Collection halts rather than continuing to spend when a run is aborted, when
every relevant record fails the output contract, or when the actor exports a
post older than the cutoff that was paid for. The halt is recorded in
`data/apify_plan.json` and no further batches start until it is cleared with
`apify_posts.py --resume-halted`.

A run-start intent is saved **before** the creation POST. If the response is
ambiguous, automatic attempts stop instead of risking a second paid creation.
Inspect Apify Console, then populate that intent file with the confirmed `id`
and `started_at` plus its saved input metadata, or remove it only after verifying
that no run started. The pipeline never automatically retries that creation POST.

Actions saves `pipeline/data` even after failure and uploads plan/batch diagnostics.
Supabase remains authoritative for activations, post records and extraction
caches. The saved plan and pending actor IDs depend on the Actions cache: eviction can lose these and cause new charges. No secrets are
stored in these reports. `APIFY_MAX_CHARGE_USD` is a per-cycle ceiling, not a
monthly budget, and does not include Google OCR/Gemini or other service charges.

## Local setup and tests

```bash
cd pipeline
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Put the same API credentials in pipeline/.env (gitignored).
.venv/bin/python run.py
```

Local limits use the same environment variables; `APIFY_TIMEOUT_SECONDS` defaults
to 1800. Never schedule local runs and Actions concurrently against one database.

The old direct collectors (`scrape_posts.py`, `following_feed.py` and login
utilities) are retained for manual rollback only. `run.py` never imports them;
production requirements no longer install Instaloader or Safari cookie tooling.
Their regression tests require the separate legacy dependencies:

```bash
.venv/bin/pip install -r requirements-legacy.txt
PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m unittest discover -s tests -v
```
