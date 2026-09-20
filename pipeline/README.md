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
| `APIFY_INCOMPLETE_RETRY_HOURS` | `8` | Wait before retrying a profile whose discovery was incomplete (at least 8 hours) |

New collection uses [hpix/instagram-scraper](https://apify.com/hpix/instagram-scraper),
ID `JER1eC8E7teQWMN3p`, pinned to build `1.2.17`, with 1 GB memory.
It requests profile posts and reels, raw media data, and no profile records.
Both `scrape_detailed_data` and `scrape_restricted_posts` are explicitly false:
their documented restricted-post event costs $0.10 per result.

`fromDate` accepts only `YYYY-MM-DD`. A verified server-side `custom_functions`
`shouldSkip` checks the native post timestamp against the precise checkpoint
before export/billing. `shouldContinue` always returns true so an old pin does
not stop traversal. `fromDate` provides the coarse pagination boundary. Unknown
or malformed timestamps are exported for validation rather than silently skipped.
If the actor exports anything older than the precise paid cutoff, collection
halts. The exact timestamp filter was checked against live output and settled
charges; relying on `item.kind` in this hook does not work in build 1.2.17.

A new post whose owner differs from the requested club gets one individual-post
lookup per shortcode in that batch to recover accepted coauthors. Saved media
IDs skip enrichment and processing. Details must preserve the exact media ID,
shortcode and timestamp and pass the same ownership and media validation.
A valid unrelated repost is skipped; a feed containing only unrelated reposts
cannot establish ownership coverage. Multiple club associations are not yet
persisted: the archive still stores one routing handle per media ID.

A profile advances only after `Finished scraping posts`, durable archival, and
no failure or cap. Null/error profile rows override completion, even if the
actor run says `SUCCEEDED`. `Scraped N/N posts` also prevents checkpoint advance.
No automatic quarantine follows a lookup failure: known real accounts failed
in the evaluation. Check failed clubs again on the normal eight-hour cadence;
use the diagnostic errors to investigate roster problems.

Already-paid official (`apify/instagram-post-scraper`, build `0.0.599`) and
legacy runs are still resumed and ingested with their own adapters and billing
checks. Official runs retain `no_items` plus explicit completion as the sole
benign error case. New paid starts use hpix. Tokens stay in Authorization headers.

The previous actor, `sones/instagram-posts-scraper-lowcost`
(`Y5mzw9TLFReI0d6gQ`), treated its `newerThan` as a pagination hint and exported
old boundary-page posts: of 5,199 billed items on 2026-09-20, 5,160 were
flagged `is_newer_than_cutoff: false`, reaching back to 2016. Its datasets also
used flattened `image_url` fields and rounded `pk` past 2**53. Both shapes are
still read so already-paid datasets stay ingestible; the composite `id` takes
precedence over `pk` because only it preserves the exact media ID.
A later test of the same build with `postsPerProfile: 5` returned exactly five
posts per profile, contradicting its documented whole-page soft limit. It
still exported old posts and an old pin; reducing the cap is not a date filter.

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

The current actor's `onlyPostsNewerThan`, together with `skipPinnedPosts`, filters
exported posts by date. The legacy actor's `newerThan` only controlled pagination.
The adapter also checks each post's timestamp. Discovery groups accounts whose individual cutoffs fall in the
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
not for refreshing known posts. By default an incomplete profile becomes eligible
again after eight hours, retaining its previous checkpoint. Healthy profiles
remain eligible every eight hours. An explicitly configured longer retry interval
still takes precedence; clear an old Actions variable set to `24` to use `8`.

**Zero duplicate Apify charges are not guaranteed.** The current actor has no
known-post exclusion list. Overlap, shared batch cutoffs, and incomplete scans
can return already-saved posts and bill them again. The old actor also billed
historical boundary-page posts. A five-minute overlap can miss posts first exposed by Instagram later than
that overlap; increase it if monitoring shows late visibility.

Raw posts are mirrored before local processing. Failed/aborted/timed-out runs,
missing profiles, malformed records, and profiles
hitting the export limit do not advance the affected checkpoints. Saved valid
posts can still be published, but the workflow exits nonzero. An empty dataset
alone does not prove coverage; the current adapter additionally requires the
explicit per-profile log acknowledgements described above. Unacknowledged
profiles remain incomplete.

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

New hpix runs reserve 80% of each batch ceiling for discovery and 20% for
conditional details. The detail run has its own durable `*-details.json` intent
and ID. Recovery resumes that paid request, even when some posts were already
saved; it never launches a replacement because the remaining shortcode set shrank.
Unused detail budget is not spent. Detail failures retain affected checkpoints.

Measured rates: $0.00099/profile post, $0.00149/individual-post lookup,
$0.00005/start at 1 GB, and zero post/profile events for a successful quiet scan.
Some lookup failures can bill $0.00299/profile despite `scrape_profile_data: false`.
The 25-profile batching means roughly 26 discovery starts per full pass when
cutoffs align, not one: about $0.117/month at three passes/day. Other cutoff
groups, detail starts, failures and overlap add to this. At the observed 1,320
new posts/month, post fees would be $1.31 before those additions; this is a
projection, not a verified monthly bill or guaranteed $0 invoice.

The retired official actor billed quiet diagnostics too: its one-row-per-check
scenario cost $157.22/month for 647 profiles at this cadence. See
[the cost investigation](../docs/apify-cost-investigation.md) for provider
comparisons, measured migration checks, and remaining reliability limits.
Charges settle asynchronously; usage read immediately after `SUCCEEDED` can
understate the final total. Batch reports include separate feed/detail run IDs
and usage. `APIFY_MAX_CHARGE_USD` covers both and remains a per-cycle ceiling.

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
