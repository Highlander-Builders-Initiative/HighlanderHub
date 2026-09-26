# Events page and pipeline code-quality audit

Audited checkout: `5a44ebd`, September 26, 2026. Product code was not changed. Existing untracked `AGENTS.md` and `CLAUDE.md` were preserved.

The architecture is workable and contains useful safeguards. The principal weaknesses are excessive data movement, work that grows with historical data rather than relevant data, and failure handling that conflates cached success or missing results with a successful live operation. A broad rewrite would introduce risk without addressing these costs directly.

## Method and scope

Traced `/events` server reads, filters, pagination, calendar, feed persistence, navigation and flyer rendering. Traced the scheduled pipeline from Apify planning/archival through extraction, assessment, transactional publication, duplicate reconciliation and notifications. Reviewed relevant SQL, tests, CI, and the installed Next.js guides for caching/navigation.

Used local tests and synthetic probes that execute current functions with external services stubbed. No live collection, OCR/model calls, production database writes, or notifications were performed. The local `last_run.json` is dated September 19 and is not evidence of current production performance. This is a code-quality audit, not a fresh production-data audit.

First-principles criteria:

- A page-sized answer should require page-sized work where possible.
- Unknown or failed data must remain distinguishable from an empty successful result.
- A cached result cannot establish the health of an external service.
- Repeated runs should converge without rewriting unchanged business data.
- Candidate matching should compare plausible peers, while retaining explicit safety exceptions.
- Optional browser persistence must not be required for basic browsing.

## Findings

### 1. P2 — Filtered pagination reads the whole active collection and can silently lose results

Locations: [filtered read](/Users/kevinlin/Documents/GitHub/HighlanderHub/src/lib/events/index.ts:307), [count source](/Users/kevinlin/Documents/GitHub/HighlanderHub/src/lib/events/index.ts:360), [initial page](/Users/kevinlin/Documents/GitHub/HighlanderHub/src/app/events/page.tsx:55).

The unfiltered query uses a database range. Applying any search, category, or day filter switches to `select("*")` without a range, applies filters in JavaScript, then slices the result. Every uncached offset repeats that read; offsets are part of the cache arguments, so the cache does not make different pages share one underlying scan. Category and date constraints, in particular, need not require downloading every active event.

This also treats a capped database response as complete. In a synthetic response-cap probe with 1,001 rows and the only matching event at position 1,001, the real read/filter function returned zero matches and `hasMore: false`. The probe emulated a 1,000-row cap; the live project's configured cap and current row count were not inspected. Two distinct filtered page calls each returned 1,000 rows from the stubbed database to produce 24-item pages.

`getEventFilterCountSource` has the same completeness issue and sends descriptions and other searchable fields for the entire returned active collection to the browser. The calendar separately limits results to 500 without pagination or a truncation marker, so a sufficiently busy range is represented as complete despite omitted events.

**Direction:** apply category/date/search predicates before database pagination, with equivalent public-host/search semantics. Return aggregate facets and calendar day counts independently of full event objects; load selected-day details as needed. If application-side filtering must remain temporarily, page its source exhaustively and distinguish partial results. Use one normalized query contract across feed/count/calendar. Preserve stable ordering and correct free-food matching.

**Acceptance:** exercise real query construction with more than the configured row limit; a match after that boundary must remain discoverable. Check complete counts and a calendar range above 500 entries. Measure rows and bytes transferred per page, including cache misses.

### 2. P2 — Cached extraction successes reset the external-service failure limit

Location: [extraction loop](/Users/kevinlin/Documents/GitHub/HighlanderHub/pipeline/extract_posts.py:486).

`extract_all` resets `streak` whenever a result is not an error. That includes an entirely local terminal-cache hit. An archive alternating failed live OCR work and cached successes can therefore keep trying the unavailable service throughout the archive instead of stopping after three actual service failures. This makes request volume, retry time and usage reservations depend on archive ordering.

A probe executed the real `process_post` path with four uncached posts alternating with four valid local caches. All four OCR calls failed; all eight posts were processed; `stopped_at` remained absent. No successful live OCR call occurred.

**Direction:** expose invocation provenance from extraction, analogous to assessment's existing `produced_live` result. Reset the relevant service-failure streak only on a successful live operation that establishes recovery. Keep cache hits, expired media and terminal skips neutral. Separate failure categories where recovery of one service would otherwise hide another service's outage.

**Acceptance:** error/cache/error/cache/error stops further paid work; a genuine service recovery resets the corresponding streak; expired URLs do not count as service outages.

### 3. P2 — Reconciliation performs quadratic work over historical rows

Locations: [full row read](/Users/kevinlin/Documents/GitHub/HighlanderHub/pipeline/db.py:111), [pair matching](/Users/kevinlin/Documents/GitHub/HighlanderHub/pipeline/reconcile_events.py:629), [late past-event check](/Users/kevinlin/Documents/GitHub/HighlanderHub/pipeline/reconcile_events.py:661).

The planner reads imported history and compares each candidate against accumulated groups. Time relevance is checked after groups have been formed, and singleton groups return before that check. `same_event` performs date parsing, venue/title normalization and other matching work for pairs that could have been excluded by a candidate index.

A synthetic probe used distinct, timed, same-venue events on separate days, all ending in 2020. It ran the current planner with a 2026 clock:

| Historical rows | `same_event` calls | Local elapsed time | Changes |
| --- | ---: | ---: | ---: |
| 100 | 4,950 | 0.151 s | 0 |
| 200 | 19,900 | 0.600 s | 0 |
| 400 | 79,800 | 2.578 s | 0 |

These are instrumented synthetic timings, not production latency. The exact comparison counts demonstrate the quadratic growth.

**Direction:** generate plausible candidates by Pacific date, content kind, and relevant identity/owner indexes; precompute reusable row features. Keep explicit paths for corrected deadlines across dates, admin merge mappings, and tombstones. Do not indiscriminately discard old rows: a previous deadline or deleted identity can constrain a current listing. The goal is bounded candidate work while preserving the existing matching policy.

**Acceptance:** all duplicate, ambiguity, lock and tombstone fixtures retain identical plans; thousands of unrelated historical rows no longer create all-pairs comparisons.

### 4. P2 — Browser storage failures can take down the events experience

Locations: [unguarded read](/Users/kevinlin/Documents/GitHub/HighlanderHub/src/lib/events/feed-session.ts:58), [unguarded write](/Users/kevinlin/Documents/GitHub/HighlanderHub/src/lib/events/feed-session.ts:157), [render-time restore read](/Users/kevinlin/Documents/GitHub/HighlanderHub/src/components/events/useEventFeedRestore.ts:39).

Storage access sits outside the JSON parsing exception guards. Snapshot writes also have no exception handling. A denied storage read propagates through the restore state initializer; a quota failure propagates from the snapshot effect. Optional scroll restoration therefore becomes a dependency of browsing itself.

Direct probes against the current exported functions confirmed that a throwing `getItem` escapes `readEventFeedRestoreState`, and a throwing `setItem` escapes `saveEventFeedSnapshot`.

The snapshot also serializes the full loaded event list on every query/filter change. The 600 ms URL debounce does not debounce these writes; larger loaded feeds increase synchronous persistence work during typing.

**Direction:** encapsulate storage access with a safe in-memory fallback, including get/set/remove operations. Keep in-memory state current immediately and persist snapshots on meaningful navigation/page changes or a bounded debounce. Preserve return-scroll/history ownership and TTL behavior.

**Acceptance:** denied storage and quota exhaustion leave browse, search and detail navigation usable; restoration degrades safely. Verify existing modal/back/forward cases.

### 5. P2 — Calendar request failures look like successfully empty days

Locations: [swallowed rejection](/Users/kevinlin/Documents/GitHub/HighlanderHub/src/components/events/useCalendarMonthEvents.ts:54), [empty-day presentation](/Users/kevinlin/Documents/GitHub/HighlanderHub/src/components/events/EventsMiniCalendar.tsx:138).

On a failed month request, the hook preserves the previous month's events, clears loading, and records the new range as attempted. There is no error result or retry action. Most dates in the new month are absent from the old dataset, so the calendar reports “no events.” Selecting a day in that same month does not change the fetch dependencies and therefore does not retry the request.

This is verified by tracing the rejection/state branches, not by a completed browser reproduction in this environment.

**Direction:** represent month data as a range-keyed loading/success/error state, expose a retry action, and prevent failed/unknown counts from being announced as zero. Preserve the existing stale-response guard; an AbortController can additionally cancel superseded work.

**Acceptance:** force the calendar endpoint to return 500, show an explicit recoverable error, then retry successfully without changing months. Rapid month changes must not display an older response.

### 6. P2 — Unchanged positive assessments still rewrite event and source rows

Locations: [update construction](/Users/kevinlin/Documents/GitHub/HighlanderHub/pipeline/assessed_events.py:300), [source upsert](/Users/kevinlin/Documents/GitHub/HighlanderHub/supabase/migrations/20260922000000_event_duplicate_hosts.sql:86), [event upsert](/Users/kevinlin/Documents/GitHub/HighlanderHub/supabase/migrations/20260922000000_event_duplicate_hosts.sql:112).

Unchanged negative decisions and some reconciled duplicates are skipped, but ordinary positive cached decisions still generate publication updates. Mapping stamps a new `scraped_at`; SQL updates source and event rows without a business-field difference check. Event updates also fire the `updated_at` trigger. This creates write traffic and modification churn even when evidence and the event projection are unchanged.

A current-function probe replayed an unchanged positive assessment on a subsequent day: `produced_live` was false, an update was generated, and its only changed event field was `scraped_at`.

**Direction:** retain transactional ownership reconciliation and missing-row repair, but suppress physical updates when persisted business fields/support are unchanged. Define observation time separately from publication/check time so a timestamp does not force a business-row rewrite. Prefer enforcing equality inside the transaction to blindly skipping all positive cache hits.

**Acceptance:** identical replay performs no unnecessary row updates; missing listings are repaired, changed evidence republishes, unlocked historical aliases retire correctly, and locked/deleted identities remain protected.

### 7. P3 — Client club search bundles unused pipeline metadata

Location: [club data imports](/Users/kevinlin/Documents/GitHub/HighlanderHub/src/lib/clubs.ts:1).

A client dependency imports both full pipeline JSON files. Browser search needs handles, labels and categories; it also receives numeric Instagram IDs and activity timestamps/source metadata. The compiled webpack client chunk contains both `instagram_user_id` and `latest_post_date`, confirming they survive compilation.

The current files contain 646 curated accounts and 829 activity handles. Compact JSON totals 169,891 bytes; projecting curated entries to handle/label/category and activity to handles totals 74,166 bytes. Gzipping those respective standalone inputs gives 29,728 versus 15,645 bytes. These figures illustrate avoidable data, not a measured production bundle reduction; the containing compiled chunk includes other code too.

**Direction:** produce a small public club directory on the server or at build time and separate the browser search helper from pipeline-data imports. Preserve activity-only accounts and current event-host names.

**Acceptance:** the production client output excludes unused pipeline fields and all current club-search regressions pass.

## Test quality and maintainability

The repository has substantial behavioral coverage, especially the Python tests and disposable-Postgres publication tests. Those are worth keeping. Several events tests, however, verify source text with `assert.match` rather than executing the Supabase query path. Examples include `tests/event-filtered-pagination.test.mjs`, `tests/event-pagination.test.mjs`, and parts of `tests/event-db-failures.test.mjs`. They can preserve a particular implementation while missing response caps or faulty retry behavior. The E2E fixture branch also bypasses the production database queries and cache wrapper.

Add behavioral tests at these boundaries instead of additional source-string assertions. Prioritize capped results, calendar failures, storage exceptions, and cached/live extraction sequences. Keep source checks only where the source-level constraint itself is the intended contract.

Smaller follow-ups, below the findings above:

- The events page requests the full summary although its UI consumes only `upcomingThisWeek`; the other two count queries are unnecessary on an events-only cold read. Other callers may still need them.
- `_generate` constructs a new Gemini client for every request. Explicit invocation-scoped client ownership would permit connection reuse and predictable closing. No leak or measurable latency regression was established here.
- Publication imports private duplicate-matcher helpers, coupling row projection to reconciliation internals. Extract a stable matching-policy interface when changing that boundary; do not split files purely to reduce line counts.

## Safeguards to preserve

The shared `ArchiveIndex` is loaded strictly before paid collection and remembers posts only after durable mirroring. Completed-prefix archival, persisted Apify plans, bounded paid attempts, and discovery-only post snapshots are useful constraints. Assessment cache provenance distinguishes live recovery from a cached decision. Publication SQL preserves locks, tombstones, support ownership and transaction rollback. Reconciliation protects ambiguous summaries and admin distinctions. The UI already has deterministic ordering, memoized cards, `content-visibility`, reusable date formatters and careful modal/scroll restoration.

Do not remove these mechanisms for brevity or add concurrency before preserving their state and budget contracts. The highest-return work is at the data and failure boundaries above.

## Verification

- Pipeline: **668 tests passed**, with `PYTHON_DOTENV_DISABLED=1`.
- App unit/integration suite: **175 tests passed**, with placeholder public Supabase variables. Initial missing-variable failures cleared with the CI-style configuration.
- ESLint: **passed**.
- Targeted offline probes: confirmed capped filtered results, repeated full reads, capped calendar/count source, escaping storage exceptions, extraction failure-streak reset, historical all-pairs matching, and unchanged positive publication updates.
- Type check: **four errors under the installed dependency tree**. Installed `react`, `react-dom`, `@types/react`, and `@types/react-dom` are 19.3.0; the lockfile specifies 18.3.1 runtimes and 18.3.x types. Errors concern nullable event refs, an accordion spread, and the `JSX` namespace. A clean lockfile installation was not performed, so these are not attributed to the committed dependency contract.
- Production webpack compilation completed after allowing the font download; its type-check step failed as above. Turbopack initially failed because the environment denied a worker port. **Browser E2E did not run**, and no browser-performance or production-build success is claimed.

Suggested order: fix extraction failure provenance and storage/calendar failure handling; replace filtered full reads with complete bounded queries; reduce reconciliation candidate work and publication no-op writes; then trim browser metadata. Resolve local dependency drift in an isolated clean install before using this machine's production-build results as a release gate.
