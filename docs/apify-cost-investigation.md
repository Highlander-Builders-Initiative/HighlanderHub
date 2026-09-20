# Instagram collection cost investigation — 2026-09-20

## Confirmed behavior

The interrupted legacy runs exported 5,199 records, including 5,160 outside
their requested date windows, for $1.5747. Most profiles produced 12 records;
none in those datasets produced 100. `postsPerProfile: 100` was a maximum
target, while `newerThan` stopped pagination after exporting an old page. The
adapter also rejected flattened image fields, preventing useful ingestion.

**Correction to the initial analysis:** the legacy actor's published
[input schema](https://apify.com/sones/instagram-posts-scraper-lowcost/input-schema)
describes a soft limit with whole-page exports. A live test of the exact
original build, `1.5.10` / `vjYY7dyBXP2zIzvW8`, contradicted that description:
`postsPerProfile: 5` exported exactly five records from each of two profiles.
Run `SmNbzOy10ShVKQNmX` cost $0.008: ten posts at $0.0003 plus $0.005 startup.
Nine records were outside the requested window. The first result for
`careersinscrubs_` was its pinned August 19, 2025 post, shortcode `DNikuzwxXrp`.
The previous official-actor tests independently marked that same post pinned.
Lowering the count helped, but did not exclude pins or eliminate repeat billing.

The official actor supports `skipPinnedPosts: true` with `onlyPostsNewerThan`.
It excludes old pins while retaining pins inside the date window, as both our
tests and its [FAQ](https://apify.com/apify/instagram-post-scraper) confirm.
The current implementation already sends those settings. Filtering pins after
downloading the dataset cannot recover charges already incurred.

## Monthly economics

The current accounts.json contains 647 profiles. Three checks per day over
30 days means 58,230 profile checks. Illustrative scenarios, not measured
monthly bills, at the account's observed event prices:

| Collection behavior | Monthly event charges |
| --- | ---: |
| Legacy actor, 12 billed posts every profile/check | $209.63 plus starts |
| Legacy actor, 5 billed posts every profile/check | $87.35 plus starts |
| Official detailed actor, one billed result every profile/check | $157.22 |

Profiles with fewer results, failures, retries and checkpoint state change
actual totals. The official actor bills `no_items` diagnostics too: test
`lC3NnqlwfHuqGY0NM` billed all 13 rows, consisting of 11 posts and two diagnostic
rows, at $0.0027 each. The $10 setting is a per-cycle ceiling, not a monthly
budget or an estimate of expected spend.

The creator's statement that CalEvents spends $1–5/month does not identify a
provider, schedule, coverage rate, or treatment of credits. Its
[public site](https://www.calevents.app/) describes 1,000+ clubs, but does not
document its collection implementation. We cannot establish his method from
that statement.

## Cheaper models tested

These are experiments, not approved production replacements:

| Actor/build | Observed cost | Coverage/contract limitation |
| --- | --- | --- |
| zaver.api/instagram-post-scraper, 1.0.6 | Earlier 11-post run: $0.01094. New quiet-window run `9OF2Ie4qabsg8Mlfa`: $0.00005 total, no post charges | No complete carousel/coauthor output in the earlier sample. New test reported an existing, readable club as HTTP 404. Errors must retain checkpoints and trigger recovery. |
| snuggly_beanie_970/instagram-public-profile-post-monitor, 0.1.7 | Run `3MDwj6vpffuiUc86M`: six posts, $0.00065 total, zero profile events with `includeProfile: false` | Correct dates/IDs for Highlander EMS and zero posts for a quiet club, but UCR CHASS was unavailable. Recent-preview depth, carousel/collaboration coverage, and repeat suppression still need validation. |

The latter's [published contract](https://apify.com/snuggly_beanie_970/instagram-public-profile-post-monitor)
supports `seenShortcodes` and filtering before billing, with $0.0001 per post
and $0.00005 per start in the inspected pricing metadata. Its optional profile
records cost $0.00049 each; enabling them for every check would add $28.53/month
at this roster/cadence. Headline post prices alone are misleading.

The three new tests cost $0.00870 total. No production records or workflow
settings were changed by these probes.

## Recommended direction

Keep a uniform freshness target for all clubs, including those quiet over
summer. Change the cost of checking, rather than using past activity to decide
which clubs deserve timely discovery:

1. Read a small recent feed page for every club on the existing eight-hour
   cadence. Do not use total post count alone as a change signal: deletions,
   reposts and collaborations can make that unreliable.
2. Compare exact IDs and timestamps against durable state, filtering before
   billable export where the provider supports it. Old pins must not end the
   chronological scan or consume the entire discovery window.
3. Continue pagination immediately when the page does not reach the previous
   boundary. A fixed five-post cap can miss a burst of six or more new posts;
   it is a safety limit, not proof of coverage.
4. Globally deduplicate genuinely new posts by exact media ID/shortcode. Use
   complete discovery metadata directly; fetch official details only when
   required fields are missing or invalid. Preserve accepted coauthors, exact
   identity, ordered carousel media, and saved-post snapshots.
5. Distinguish a successful quiet check from a failed request. Retain failed
   checkpoints and use bounded retries/fallback; do not silently call a failure
   an inactive club. Record cost and coverage of those fallbacks separately.

A provider with free quiet checks makes cost scale mainly with new posts.
For example, at the measured Zaver discovery rate plus $0.0027 detailed
enrichment, 1,000 newly discovered/enriched posts would cost $3.69 plus starts,
overlap, failed attempts and recovery. This is an economic illustration;
that two-stage pipeline has not been validated end to end.

Enrichment is conditional, not an unavoidable fee. At Snuggly's measured
$0.0001/post rate, 1,000 complete new posts would incur $0.10 in post charges.
With `e` posts needing official enrichment, that becomes `$0.10 + $0.0027 × e`,
before starts, repeated exports, recovery and fallback discovery. A 5% fallback
rate across 58,230 checks would itself cost $7.86 at just one $0.0027 result per
fallback. Cheap discovery alone therefore cannot establish a $5 monthly budget.

Global processing deduplication already exists: `known_post_ids()` reads exact
media IDs from Supabase, and a within-run set suppresses duplicate archives.
These checks prevent repeated OCR/assessment, but do not refund actor charges.
The current post table stores one routing handle; persisting every accepted
club-to-post association is a separate data-model change, not already supported.
Never infer an accepted collaboration merely from a post appearing in a feed.

For a future monitor, send a bounded recent set of known shortcodes covering
each requested date window, plus relevant known pins; keep complete canonical
history in Supabase. Check returned IDs against that full history regardless.
Do not advance a checkpoint to evict old IDs or clear a failure. If the recent
set must be truncated, the consequence can be repeat billing, never permission
to drop newly discovered posts. Check all clubs uniformly and record failures,
retry attempts and provider used independently from last successful coverage.

An owned HTTP collector with bandwidth-priced proxies is another route that
avoids per-result fees. For illustration, 58,230 checks averaging 40 KB of
billable traffic would consume 2.33 GB before retries, extra pages and details.
[DataImpulse's published minimums](https://help.dataimpulse.com/en/articles/15930995-minimum-payment-and-plan-sizes-explained)
list standard residential traffic at $1/GB, a one-time $5 introductory purchase,
then a $50 minimum purchase with non-expiring traffic. That is a consumption
model, not a verified Instagram reliability or monthly-cost estimate. It also
requires maintaining the collector and validating access from GitHub Actions.
Account separately for profile resolution, metadata, pagination, redirects,
retries and detail calls. Image downloads must not be assumed to fit the 40 KB
metadata example. Prefer public, unauthenticated collection; no personal session
cookies are needed for the probes here or proposed as the default pipeline.

The acceptance test for any replacement is a representative roster comparison:
active, quiet, newly active, pinned, collaboration, carousel and burst cases;
repeat runs with no new posts; explicit failures; and total cost including
fallbacks. The cheap candidates above have not passed it. Neither a promised
$5 budget nor zero missed events is justified by the current evidence. Even a
healthy eight-hour poll can miss an event announced shortly before it starts.

## Quantitative follow-up — 2026-09-20

The offline evaluator `pipeline/evaluate_apify_monitor.py` compares saved
official reference rows with monitor rows and logs. It makes no network or
database writes. It measures agreement with a reference snapshot, not absolute
Instagram recall, and never treats a preview fetch as proof of pagination.

New runs, all terminal, with settled charges read back from Apify:

| Run | Input | Cost |
| --- | --- | ---: |
| `2wxcfk3gw31RV2A6y` | Snuggly 0.1.7; five profiles; since September 1; limit 100; no profile rows | $0.00065 |
| `ZYuzsod7HNYA6LeaN` | Same input plus the six returned `seenShortcodes` | $0.00005 |
| `oFinSA0g9nPMS5JMC` | Official 0.0.599 reference; three profiles; same cutoff; limit 30 | $0.06750 |

Total: **$0.06820**. The official reference ran minutes after the first monitor
run, so this is a short-interval comparison, not simultaneous ground truth.
Both actors returned six Highlander EMS posts. There is no evidence here of a
hidden six-post cap. The official reference also found 18 athletics posts and
one Reach Initiative post; the monitor reported those profiles unavailable.

| Metric | Measured result / remaining gap |
| --- | --- |
| Public profile retrieval | First monitor run: 2/5 (40%); repeat: 0/5. A fetched preview still does not certify complete coverage. |
| Reference new-post recall | 6/25 (24%) across the three freshly compared profiles; 19 missed through explicit retrieval failures. This is not a roster-wide estimate. |
| False quiet | No explicit successful-zero claim contradicted the fresh reference. However, the repeat dataset was empty while all five profiles failed; ignoring logs would create false quiet. |
| Duplicate billing / repeat cost | Repeat cost $0.00005 with zero post charges, but every retrieval failed. Seen-ID suppression remains **unverified**, not passed. |
| ID, timestamp, caption fidelity | 6/6 exact matches on the overlapping image posts; all six passed the existing archive normalizer through the experimental adapter. |
| Carousel fidelity | Unverified: the reference had three carousels, but their profile failed in the monitor. No matched carousel sample. |
| Coauthor fidelity | Unverified: no matched collaboration sample. Presence of an advertised field is insufficient. |
| Old pin handling | Quiet pinned profile returned zero recent posts in the first run; repeat failed. Explicit pin-order/crowding and in-window pins still need matched tests. |
| Burst recall | Six reference posts were found; 18 on another profile were missed because retrieval failed. Pagination across 10/20-post bursts remains unverified. |
| Incremental new-post cost | Six exported posts charged $0.0006 plus $0.00005 startup. A controlled one-new-post transition has not been observed. |
| Latency | Posting-to-discovery delay unmeasured; run duration is not that metric. |

The evaluator reports unavailable and unacknowledged profiles separately from
successful-zero claims, counts missing shortcodes, compares ordered child IDs
and coauthor identity when matched samples exist, and uses `null` for metrics
without samples. Run it against downloaded JSON/log files, for example:

```sh
PYTHON_DOTENV_DISABLED=1 pipeline/.venv/bin/python pipeline/evaluate_apify_monitor.py \
  --reference reference-items.json --candidate monitor-items.json \
  --log monitor.log --profiles highlanderems ucr_athletics thereachinitiative.ucr \
  --cutoff 2026-09-01T00:00:00Z
```

For repeat evaluations, add `--seen seen-shortcodes.json` containing exactly the
JSON array supplied to that run. Intentionally suppressed IDs are excluded from
the expected new set, while any re-export is counted. Billing must be checked
against settled run metadata, not inferred from dataset length.

**Hard invariant implemented:** the official collector now accepts only
`no_items` plus explicit completion as a successful empty window. A different
error cannot be overridden by a completion log; its checkpoint stays unchanged.
Regression tests cover not-found, blocked, rate-limited and unknown errors.

**Decision:** keep the production provider unchanged. The cheap actor can
supply directly usable image-post data, but failed this coverage gate. Retry
and fallback costs must be measured before claiming the proposed savings.

## Provider search — 2026-09-20

### Method

The Apify store lists 434 distinct Instagram actors; 429 price per event and
five bill only platform compute. Filtering to profile→posts collection leaves
116 candidates. Ranking them by headline post price is the wrong test for this
workload. At 647 profiles and three checks a day, roughly 56,900 of the 58,230
monthly profile-checks are quiet, so the monthly bill is dominated by **what a
provider charges for a profile with nothing new**, not by its per-post rate.
A provider that emits one billed diagnostic row per quiet profile cannot reach
$5/month at any plausible post price.

Ground truth came from `data/posts`, which the production collector already
wrote, so measuring recall cost nothing. The test roster was 42 profiles:
36 with archived posts between 2026-09-14T00:00Z and the archive's own
freshness boundary of 2026-09-20T17:33Z (164 posts, including 52 carousels and
13 collaboration posts owned by another account), plus six clubs silent since
2026-09-01 to price a quiet check. Posts newer than that boundary are excluded
rather than counted against a provider. Every probe carried `maxTotalChargeUsd`.
All probes together cost **$0.8970**, settled.

### Candidates measured

| Actor / build | Run | Cost | Outcome |
| --- | --- | ---: | --- |
| apidojo/instagram-scraper 0.0.1067 | `UMifyZmEgSHys6MTk` | $0.00500 | Refuses more than 10 items per run on the Free plan; 9.8M lifetime runs make it the strongest candidate on a paid plan only |
| sones/instagram-posts-scraper-lowcost 1.5.10 | `rSbN3a226eRz3wfHb` | $0.08000 | Exported 916 rows in 37s ignoring `newerThan`, and aborted on the charge ceiling |
| snuggly_beanie_970/…post-monitor 0.1.7 | `3iQhAsZYa51alKPaa` | $0.00245 | 4 of 42 profiles retrieved, 38 unavailable; 20/164 recall. The five-profile result was not unlucky |
| fetch_cat/instagram-profile-posts-scraper 0.1.30 | `8cf6YAxeZyyHrdhD8` | $0.01682 | 138/164; bills a profile row on every check; timestamps disagreed on 87 of 138 matches, once by 48.9 hours |
| apple_yang/instagram-post-scraper 0.0.40 | `fhrQb30eH1jz3G9PA` | $0.25500 | 153/164 with exact timestamps, types and carousels — but emits an empty billed row per quiet profile, the official actor's failure mode at $0.0015 |
| hpix/instagram-scraper 1.2.17 | `rEtKuzxmySCic5RwL` | $0.17429 | 161/164 found; 151/164 through the full ingestion contract |

`scrape_reels` defaults to true and must stay true: with reels off the same
actor returned 106/164, and all 54 extra misses were videos.

No provider returned `DdVAIo1uGrL`, `DdU4JxoMfiG` or `DdasXqaIwDr`. Three
independent providers missing the same three archived posts makes deletion
plausible, but does not establish it; shared visibility limitations are another
possibility. They remain unexplained misses against the archived snapshot. Of the 161 posts any
provider returned, hpix returned all 161.

### hpix/instagram-scraper

| Gate | Measured result |
| --- | --- |
| Profile retrieval, 42-profile roster | 42/42 |
| Profile retrieval, full 647-club roster (`l5u9pxGwdctAQuVUi`) | 644/647 finished in 369s in one actor run; 3 failures, all real accounts. This does not measure the production batch plan. |
| Reference recall | 161/164 found; 151/164 also satisfy roster ownership |
| ID, timestamp, caption, type fidelity | 151/151 exact |
| Carousel slide order | 50/50 ordered `media_key` lists identical |
| Old pins | Walks past them; `enginuity_ucr` paginated back to a 2024-09-22 post before stopping |
| Quiet check | `wSVdchPZZbFthyyWW`: zero rows, all 42 finish lines, **$0.00005 for the whole run** |
| Failure signalling | A `kind: "profile"` row with a null body, plus a missing `Finished scraping posts` line |
| Failure billing | `qwnxJWI6n5WCVF5Bd`: five fabricated handles billed 5 × $0.00299. The three real-but-unreachable accounts in the full-roster run billed nothing |
| Burst recall | `deltagamma_ucr` returned all 19 posts of a 6.7-day window; `posts_per_account` is the only cap |

It returns raw Instagram GraphQL nodes — `taken_at_timestamp`, `owner`,
`coauthor_producers`, `edge_sidecar_to_children`, `display_resources`,
`pinned_for_users` — so `normalize()` accepts them unchanged through the
adapter now in `evaluate_apify_monitor.py`.

Run production-safe: `scrape_detailed_data: false` and
`scrape_restricted_posts: false`. Both are documented to bill at the
`restricted_post_scraped` rate of **$0.10 per post**. With detailed data on,
`Ud9dXdOQANznP4zWh` was still billed at the ordinary rate, but a $0.10 event
must not depend on an unenforced discount, and turning both off changed
nothing: identical 161/164 recall, identical fields, identical cost.

### Cost

| Component | Rate | Monthly |
| --- | --- | ---: |
| Actor starts, 3/day | $0.00005 | $0.0045 |
| New posts (~1,320/month at the archive's current rate) | $0.00099 | $1.31 |
| Collaboration detail lookups, 13 of 176 rows | $0.00149 | $0.15 |
| Quiet profile-checks (~56,900/month) | $0 | $0 |
| **Total** | | **≈$1.46** |

That sits inside the Free plan's $5 monthly credit, so the expected invoice is
$0. Two things can move it: a dead roster handle bills $0.00299 per check until
it is pruned or quarantined, and `restricted_post_scraped` is a $0.10 event
that only the two input flags above keep at zero. Keep `maxTotalChargeUsd` set.

### The one gap: collaboration attribution

The profile feed returns `coauthor_producers: []` even on posts that are on the
club's grid under another account's name, so `normalize()` rejects them — 15 of
176 rows, 13 distinct posts. Nine of those posts are owned by another roster
club and still arrive through that club's own feed; four are owned by accounts
outside the roster and would be lost.

The actor's individual-post mode recovers them. `4h1A6UotNOBCYEJbB` fetched all
13 shortcodes for $0.01942 and returned the native private-API shape — composite
`id`, `pk`, `code`, `media_type`, `carousel_media`, `image_versions2` — with
populated `coauthor_producers`. Feeding those to the existing `normalize()`
produced 17 club-attributed records from 13 posts, including one post correctly
attributed to four clubs. So enrichment stays conditional: fetch a detail only
when a feed row's owner is not the requested handle.

Persisting more than one club per post is still the separate data-model change
this report has noted throughout. Until it lands, the second attribution is
recoverable but not storable.

### Reproducing

```sh
PYTHON_DOTENV_DISABLED=1 pipeline/.venv/bin/python pipeline/evaluate_apify_monitor.py \
  --reference archive-records.json --reference-format archive \
  --candidate hpix-items.json --candidate-format hpix \
  --log hpix.log --cutoff 2026-09-14T00:00:00Z --profiles <handles>
```

`--reference-format archive` reads records this pipeline already wrote, so a
comparison costs nothing. For hpix the evaluator now reports `scan_completed`
and `pagination_to_cutoff_verified` from the `Stopping at post X (taken at D)`
line, counting a profile only when `D` is older than the requested cutoff; a
null profile row overrides any finish line, the way `no_items` does for the
official build.

### Decision

The production provider stays unchanged; this is a measurement, not a
migration. hpix/instagram-scraper is the first candidate to clear the coverage
gate and the quiet-check cost gate at the same time, at roughly $1.46/month.
What remains before a switch is a migration in `apify_posts.py` — the adapter,
the null-profile-row invariant, conditional detail enrichment, dead-handle
quarantine — and observation over a stretch of real cycles. One run of 647
profiles is not a track record, and the actor has 20,282 lifetime runs against
apidojo's 9.8 million.


## Migration implemented and checked — 2026-09-20

New starts now use hpix build 1.2.17. Already-paid official and legacy runs
remain resumable. The shared hpix adapter lives in `pipeline/hpix_contract.py`
and is used by both collection and offline evaluation. All expensive optional
modes are disabled, reels remain enabled, and missing/error profiles never
become successful quiet checkpoints.

An additional integration issue changed the implementation: `fromDate` rejects
ISO timestamps and accepts only whole calendar dates. Passing midnight alone
would repeat earlier same-day posts. The migration sends that date for
pagination and a native timestamp predicate in `custom_functions.shouldSkip`
for exact pre-export filtering. The hook receives native post data, so a
predicate guarded by `item.kind === 'post'` silently fails to filter this build.
`shouldContinue` stays true, preserving traversal past old pins. Unknown timestamp
shapes are retained for contract validation, not treated as safely skippable.

Live checks, costs read back after settlement:

| Run | Result | Cost |
| --- | --- | ---: |
| `RQkq0AR4feJ4APVqZ` | Initial envelope-shaped filter failed: 8 rows, including 2 before the timestamp cutoff | $0.00797 |
| `39YP3I0mcvYzXddDE` | Unconditional skip: zero rows and zero post events; hook is active | $0.00005 |
| `iQArSmP9IXnYAhvvu` | Adding the second hook did not fix the envelope predicate | $0.00302 |
| `JpcrS2lA1jFrIWUHl` | Diagnostic skip-all check; zero post events | $0.00005 |
| `cgNrx2bmaW8nani9j` | Corrected native timestamp filter: 2 recent posts, earlier same-day post excluded; 2 post charges | $0.00203 |
| `pXyx8JIJ4PAA3Vo3E` | Actual migrated collector: four profiles, six posts, exact cutoff, one quiet profile | $0.00599 |
| `xUgCQ4YMirdzwfF7o` | Its conditional enrichment: three cross-owner posts, all accepted as collaborations | $0.00452 |

Total additional validation: **$0.02363**. Actual collector smoke test:
**$0.01051**, six archived candidates and four successful checkpoint candidates.
Database/archive writes, OCR and publication were mocked; production records
were not changed. Earlier timestamp-schema requests returned HTTP 400 before
starting an actor.

Replaying the saved 42-profile safe dataset and saved individual-post results
through collection produced **169 distinct accepted posts, all 42 profiles
complete, no errors**. This total includes posts newer than the earlier
164-post archive reference window; it must not be described as 169/164 recall.
The replay also established that individual detail rows can have `kind: reel`,
and that one CHASS feed item was a valid unrelated repost rather than a club
collaboration. Those posts are fully validated and skipped; a feed with only
unrelated posts cannot prove ownership coverage.

Unknown cross-owner posts are enriched once per shortcode per batch, with
identity, timestamp, accepted coauthor and media validation. Durable known IDs
prevent repeat enrichment/processing across completed batches. The current
single-handle archive schema is preserved; multi-club relationship storage is
still a separate change.

Each existing batch ceiling is split before any spend: 80% discovery, 20%
details. Both run IDs/intents are durable; ambiguous starts are never retried.
Aborts, restricted-post charges and date-contract violations stop later paid
batches. Other profile/detail failures retain checkpoints and retry at the
normal eight-hour cadence by default. Explicitly configured longer retry
intervals remain honored. No automatic dead-handle quarantine is enabled:
known real accounts failed in the full-roster probe, so a provider error alone
is insufficient evidence to disable a club. Failure rows remain visible for
roster review, including potentially billable not-found errors.

**Historical cost correction (25-profile planner):** those batches needed roughly 26 starts per
full pass when cutoff groups align, adding about $0.117/month rather than
$0.0045. At the sampled post rate, feed posts + the proposed collaboration mix
+ these starts are roughly **$1.57/month**, before extra cutoff groups, detail
starts, overlap, retries and failures. School-year activity can materially
increase this. The free credit is shared with other usage, including tests;
an expected $0 invoice is not established by this projection. Observe real
cycles before treating a monthly budget or failure rate as reliable.

Activation requires these code and workflow changes to reach the scheduled
branch. Existing halted plans still require review and `--resume-halted`;
this migration does not clear a previous halt or start a production run.


### Planner follow-up: small batches and stale-first scheduling

The local enabled roster reproduces 647 checkpoints, 455 marked incomplete,
and 28 old-planner batches: 24 of size 25 plus 20, 22, 1 and 4. New plans group
up to 100 profiles within each cutoff hour and run oldest first, yielding nine
batches on that snapshot. Each batch reserves at least $0.25 before the remaining
cycle ceiling is weighted by profile count; the smallest snapshot batch gets
$0.30. The combined ceiling stays $10. Both local and Actions collection time
defaults are now 3600 seconds, with an Actions variable override.

Only posts-only detail runs drop profile-event headroom: feed lookup failures
can still charge profile_scraped and keep that safeguard. Detail output uses
the individual-post price when billing counters lag. Missing feed run options
fall back to its 80% reservation, not the whole feed-plus-detail batch ceiling.

The surrounding audit also fixed missing coauthor metadata being mistaken for
an unrelated repost, malformed detail rows stranding paid dataset replay, and
case differences allowing a completion log to override a failure or cap.
Regression tests exercise these paths without starting paid actors. Larger-batch
runtime remains unmeasured; existing saved plans retain their original reservations.
The earlier 25-profile start-cost projection above is historical. Seven aligned
100-profile batches imply about $0.0315/month in feed starts at three cycles/day,
before extra cutoff groups, details, overlap and retries.
