---
target: events page
total_score: 29
p0_count: 0
p1_count: 2
timestamp: 2026-05-23T11-08-01Z
slug: src-app-events-page-tsx
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Loading state uses a pulsing dashboard-style dot; status messages could be quieter / skeletal. |
| 2 | Match System / Real World | 4 | Day-window labels, time formats, calendar pattern all match user mental models. |
| 3 | User Control and Freedom | 3 | No keyboard shortcuts (no `/` or `⌘K` for search). No "back to top" after infinite scroll. Calendar deselect unclear. |
| 4 | Consistency and Standards | 3 | Day-of-week initials and the "Today" eyebrow use uppercase + tracking, which directly violates the codebase's Quiet-Label Rule. Time-period (AM/PM) uses display font while digits use mono — mismatched faces inside the same atom. |
| 5 | Error Prevention | 3 | No nudge when filters narrow to zero; calendar fetch errors are silent. |
| 6 | Recognition Rather Than Recall | 3 | Active filters are signaled only via rail highlight state — no enumerated chip-bar showing what's actively scoping. The `resultsLabel` says "X events matching" without listing the filters. |
| 7 | Flexibility and Efficiency | 2 | Filter state is not persisted in the URL — a Free-Food-Weekend view can't be bookmarked or shared. No keyboard shortcuts. No way to share a deep-linked filtered view, which is a notable gap for a tool whose explicit purpose is coordination. |
| 8 | Aesthetic and Minimalist Design | 3 | Surface is restrained and monochrome, hierarchy is clear, but the summary line is hero-metric prose (the explicit anti-reference) and the empty state is generic-SaaS (dashed border + centered + pill). |
| 9 | Error Recovery | 3 | Load-more failure has coral status + Retry. Other failure modes (calendar fetch, search-returns-zero in narrow category) are silent or generic. |
| 10 | Help and Documentation | 2 | No inline guidance for what counts as each category or how "Today / This Week / Weekend" differ. No help affordance. Acceptable for a small product, worth flagging. |
| **Total** | | **29/40** | **Solid product UI with room to climb.** |

## Anti-Patterns Verdict

**LLM assessment**: The events page is *mostly* on-voice. It reads as an editorial bulletin browser, not a SaaS dashboard, and the time-anchor card layout is genuinely distinctive. But there are a small number of SaaS / dashboard reflexes leaking through that pull the surface toward generic — and notably, two of them are direct violations of the project's own `DESIGN.md`. The pattern is: tasteful structure, with three or four "default Tailwind component" moments that didn't get the same care.

**Deterministic scan**: The bundled `detect-antipatterns.mjs` engine is missing from this install (`detect.mjs` references it but the file doesn't ship). Fell back to grep-based checks against the absolute-bans list and `DESIGN.md` named rules. Findings:

- `EventsMiniCalendar.tsx:97` — `text-[10px] font-medium uppercase tracking-[0.04em]` on day-of-week initials. **Direct violation** of the Tracking Rule.
- `EventsFeedColumn.tsx:197` — `font-body text-[12px] font-medium uppercase tracking-[0.06em]` on the "Today" eyebrow. **Direct violation** of the same rule.
- `EventsMiniCalendar.tsx:59` — `animate-pulse rounded-full bg-sky` as a loading indicator. Dashboard reflex; not in the absolute-bans list but tonally off-voice and overlaps with the project's saved feedback about pulsing indicators on editorial surfaces.
- `EventsMobileFilterSheet.tsx:136` — `shadow-[0_-12px_40px_rgba(15,17,21,0.18)]` exceeds the Quiet-Shadow Rule's 0.08 opacity ceiling. Bottom sheets often want a heavier shadow, but this is over the doctrine cap.
- `src/app/events/[id]/page.tsx:219` — backdrop-blur on a fixed bottom action bar (on the event-detail route, out-of-scope for this critique). Worth noting that this is a *fourth* glass surface in the codebase beyond the three sanctioned in the Three-Glass Rule.

False positives flagged from the grep: an em dash in a `ShareButton.tsx` comment (not UI copy); the sanctioned glass + halo on the sticky filter bar (explicitly allowed); a hairline `border-r` on the time-column (1px, not the side-stripe pattern).

**Visual overlays**: not applicable — no browser-automation tooling in this session, so no live overlay rendered.

## Overall Impression

This is a competent, editorial-flavored events browser doing genuinely thoughtful things — the time-anchor card column, the calendar's per-day category dots, the mobile sheet's proper focus trap. The biggest issue isn't structural; it's that a handful of "default Tailwind" moments slipped through and undercut the otherwise carefully edited voice. The summary metric line, the pulsing loading dot, the tracked-uppercase eyebrows, and the dashed-border empty state are each individually small, but together they tell on the page as "AI-assisted product UI." Pull those four toward the editorial voice the rest of the page already commits to, and the surface jumps a tier.

Single biggest opportunity: URL state. For a tool whose stated purpose is "scannable bulletin for coordinating with others," not being able to share `/events?cat=free_food&when=weekend` is a real product gap, not just a craft gap.

## What's Working

1. **Time-anchor card column.** The left-edge time block (big mono digit + smaller display-period) is genuinely distinctive — reads like a printed program guide, not a list-of-cards. It gives the eye a typographic spine the entire feed hangs on.
2. **Mini-calendar with category dots.** Most calendars use a single dot to mean "something on this day." Encoding category color into up to three dots gives a glanceable density-by-type signal without taking more space. Quiet, non-obvious, well-considered.
3. **Mobile filter sheet engineering.** Body-scroll lock, focus trap, focus restore on close, Esc to dismiss, custom ease-out keyframe — the boring details done right. Most teams ship this with at least two of these missing.

## Priority Issues

**[P1] Summary line is hero-metric prose** — `EventsFeedColumn.tsx:69–73`
- **Why it matters**: "{N} campus gatherings, with {N} happening this week and {N} serving free food" is the "10,000+ events tracked" SaaS template wearing a sentence-case suit. Both `PRODUCT.md` and `DESIGN.md` explicitly call this out as an anti-reference. It's the first thing a user reads under the H1; if anything sets the tone, this does, and right now it sets the wrong one.
- **Fix**: Replace with editorial intro. Either a quiet dateline ("Friday, May 23 · 24 events queued") or a behavior-oriented sentence ("Everything happening this week. Filter, scan, RSVP."). The counts already live in the day-section subheaders and filter-rail counts — they don't need to be triple-stacked at the top.
- **Suggested command**: `/impeccable clarify` (focused on the summary copy + tone), then a small `/impeccable layout` pass to rebalance once the metric prose is gone.

**[P1] Pulsing loading dot in mini-calendar** — `EventsMiniCalendar.tsx:51–62`
- **Why it matters**: `animate-pulse rounded-full bg-sky` is the canonical "live indicator" reflex. The project explicitly flagged this aesthetic as off-voice on editorial surfaces. Calendar data loads in well under a second — a pulsing dot is overkill *and* off-brand. Adds visual noise to a sidebar that should disappear into the task.
- **Fix**: Remove the visual indicator entirely; the `role="status"` text already announces loading to screen readers. If a visual cue is genuinely needed, dim the calendar dots to `opacity-50` while loading, then fade them back to full opacity when data arrives — a state change tied to the actual content rather than a free-floating signal.
- **Suggested command**: `/impeccable quieter` on the calendar's loading affordance.

**[P2] Tracked-uppercase labels violate the project's own Quiet-Label Rule** — `EventsMiniCalendar.tsx:97`, `EventsFeedColumn.tsx:197`
- **Why it matters**: `DESIGN.md` is unambiguous: "Don't decorate labels, eyebrows, taglines, or section headers with `uppercase tracking-[...]` in any font. That pattern is the SaaS / dev-tool reflex the AI Slop Test rejects." Both the calendar day-initials row and the "Today" eyebrow on the current day's header do exactly this. The codebase has a saved rule against this exact pattern.
- **Fix**:
  - Day-of-week initials: `text-[11px] text-muted` in sentence case ("Sun Mon Tue") *or* keep single letters but drop uppercase + tracking — `text-[11px] font-medium text-muted/80` with no `uppercase` or `tracking-[...]`.
  - "Today" eyebrow: drop the uppercase + tracking. Either `text-[13px] font-medium text-ink/55` in sentence case, or remove the eyebrow entirely and lean on the heading position (it's already the top section).
- **Suggested command**: `/impeccable typeset` on those two callouts.

**[P2] Empty state is generic-SaaS** — `EventsFeedColumn.tsx:164–182`
- **Why it matters**: Dashed border + centered "No matches." + filled-pill CTA is the textbook empty-state template. `PRODUCT.md` explicitly: "Empty states are honest, not padded" and "teach the interface, not 'nothing here.'" Current empty state does the opposite — it removes information instead of replacing it with guidance. A user who landed on this empty state cannot tell *which* of their filters is too narrow.
- **Fix**: Make the empty message conditional on the active filters. "Nothing in Free Food this weekend. Widen 'When' to next week, or clear the category." Drop the dashed border (looks like an upload zone). Lean on a hairline divider above + spacious type, no container chrome. The "Submit your own event" prompt below it is good — keep that.
- **Suggested command**: `/impeccable onboard` (covers empty-state design specifically), or `/impeccable clarify` if the copy is the primary concern.

**[P3] No URL state for filters** — `EventsBrowser.tsx` (state lives entirely in `useState`)
- **Why it matters**: A campus bulletin whose explicit purpose is *coordination* should let two students share "free food this weekend" by sharing a URL. Right now: cannot bookmark, cannot share, cannot deep-link from an Instagram caption. This is a product capability gap dressed as a state-management choice.
- **Fix**: Sync `category`, `query`, and `dayWindow` to URL search params via `useSearchParams` + `router.replace` with `{ scroll: false }`. Read params on mount. Debounce `query` writes (the search input already has a 600ms timer for analytics — reuse it).
- **Suggested command**: `/impeccable harden` (production-readiness pass — URL state, edge cases, error envelopes).

## Persona Red Flags

**Alex (Power User)** — student who checks Hub three times a week:
- No `/` or `⌘K` to focus search. Must tab through nav + categories before reaching the input.
- No URL-shareable filter state. Can't bookmark "weekend free food."
- Infinite scroll without back-to-top means re-finding a card after scrolling is friction.

**Jordan (First-Timer)** — student who landed here from an Instagram story link:
- The summary metric line tells Jordan the count, not what Hub *is* or what they should do. "X gatherings, Y this week, Z free food" is a stats line, not an orientation.
- The pulsing calendar dot will read as a notification badge to a first-timer ("something happened, I should look at it"), then resolve into nothing.
- Empty state, if triggered, gives no diagnosis — Jordan won't know which filter is the problem.

**UCR undergrad on phone between classes** (project-specific persona from `PRODUCT.md`):
- Mobile filter sheet works well, but every filter action costs at least 2 taps (open sheet, tap option, dismiss). The most common scope ("today" / "this week") could be exposed inline on mobile, under the search bar, so it's one tap.
- The 88px flyer thumbnail on each card is a nice touch on mobile but the time column + thumb + text squeezes content to a fairly narrow column on a 360px viewport. Title `line-clamp-2` is good defense, but a one-line scan is still tight.

## Minor Observations

- AM/PM period on each card is `font-display font-semibold text-muted`, but the digit beside it is `font-display font-semibold ... tabular-nums`. Both are display, which is consistent, but the *digit* should arguably be mono per `DESIGN.md`'s "IBM Plex Mono carries numerics" rule. As-is, mono never appears in the time atom, but appears in the category-count digits in the filter rail. Worth pulling the time digit into mono so numeric content is uniformly mono.
- Mini-calendar's "Today" button is text-only at 12px muted; flanking prev/next arrows are 28×28 buttons. The "Today" target is hardest to hit despite being the most-likely-used affordance in that cluster.
- `formatPacificMonth(cursor).toLowerCase()` → "may 2026" is a deliberate editorial lowercasing, but it sits next to UPPERCASE day-of-week initials. Pick one register and commit.
- "Scroll for more events" sentinel text is fine but a bit literal; "More below" or even a chevron-only sentinel would read calmer.
- The `loadedCount` analytics passthrough into every `EventCard` is good for return-restore but means a prop drills through the entire feed. Acceptable, but worth memoizing if the feed grows large.
- Result-count `aria-live="polite"` is correct; the value updates frequently as user types in the search input. Consider debouncing the announcement to avoid screen-reader spam during a fast-typing session.

## Questions to Consider

- What if filter state lived in the URL? Would that change how the page is shared — and how often?
- What if the summary line were a dateline instead of a stat-block? ("Friday, May 23. 24 events on the wall this week.")
- What if the empty state diagnosed which filter caused the zero result, instead of just offering "Clear filters"?
- What if "Today" / "This Week" / "Weekend" were inline on mobile, not buried behind the Filter button?
- What if every numeric element on the page used Plex Mono uniformly — including the time digit on each card?
