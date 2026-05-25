---
target: events page
total_score: 33
p0_count: 0
p1_count: 1
timestamp: 2026-05-23T11-49-54Z
slug: src-app-events-page-tsx
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 4 | Pulsing dot gone; calendar loading is a quiet opacity fade; `aria-live="polite"` on results. |
| 2 | Match System / Real World | 4 | Day-window labels, time formats, calendar pattern all match mental models. |
| 3 | User Control and Freedom | 3 | URL state landed. Still no `/` or `⌘K` keyboard shortcut for search. Still no per-chip filter removal. No back-to-top after infinite scroll. |
| 4 | Consistency and Standards | 4 | Tracked-uppercase eyebrows gone. Mono now used uniformly for numerics. Lowercase month + lowercase day-initials are now mutually consistent. |
| 5 | Error Prevention | 3 | Empty state now diagnoses the cause (9 branches via `diagnoseEmpty`). Calendar fetch error still silent. |
| 6 | Recognition Rather Than Recall | 3 | Active filters still signaled only via rail highlight. No removable chip bar enumerating active scopes above the feed. |
| 7 | Flexibility and Efficiency | 3 | URL state landed. No keyboard shortcuts. No back-to-top. Would be a 4 with shortcuts wired. |
| 8 | Aesthetic and Minimalist Design | 4 | Hero-metric prose, dashed empty state, pulsing indicator, tracked-uppercase eyebrows all gone. |
| 9 | Error Recovery | 3 | Load-more failure has coral status + Retry. Calendar fetch failure has no surfaced recovery. |
| 10 | Help and Documentation | 2 | No legend for the mini-calendar's per-day category dots. |
| **Total** | | **33/40** | **Up from 29/40.** |

## Anti-Patterns Verdict

**LLM assessment**: The page no longer reads as AI-assisted. Every reflex pattern the prior critique flagged has been addressed. Summary line is an editorial dateline, not a stat block. Empty state diagnoses *which* filter is the problem with nine conditional headlines. Calendar uses a quiet opacity fade. Day-of-week initials are lowercase, no tracking. "Today" eyebrow is sentence-case Bricolage. The time-anchor card design reads like a printed program guide. Remaining tells are interaction-level (touch targets, chip-bar, legend), not aesthetic-level.

**Deterministic scan**: Bundled `detect.mjs` still reports `bundled detector not found`. Fell back to grep against absolute-bans + DESIGN.md named rules.

- `uppercase` + `tracking-[...]` decorative label pattern: 0 instances (was 2).
- `animate-pulse` as a status indicator: 0 instances (was 1).
- `border-l-` / `border-r-` > 1px colored stripe: 0 instances.
- Glass surfaces: 1 instance (sticky filter bar) — sanctioned under the Three-Glass Rule.
- Shadow opacity ceiling: sticky bar 0.06, mobile sheet 0.08 — both within the 0.08 cap (mobile sheet was 0.18 last run).
- Em dashes in UI copy: 0.
- **Touch targets below 44×44**: 6 instances across filter and calendar UI. See [P1].
- **DESIGN.md drift**: category rail removed from `EventCard.tsx` but still documented in DESIGN.md as the signature side-stripe.

**Visual overlays**: not applicable — no browser-automation tooling in this session.

## Overall Impression

The 4-point jump from 29 to 33 is real. Every priority issue from the prior run was addressed, and addressed well. The time-column-as-anchor card design is the single best move; it gives the feed a typographic spine. Remaining work is two tiers smaller than what just shipped. Single biggest live gap: mobile touch targets on the very surface PRODUCT.md commits to mobile-first.

Strategic question: the category rail is gone. The commit framed it as removing "monochrome category rail" — but DESIGN.md treated that rail as the load-bearing reason for scannability-by-hue. Either DESIGN.md is now stale, or the rail's removal sacrificed something worth restoring with a quieter affordance.

## What's Working

1. **Editorial dateline replaces the stat block.** `Friday, May 23 · 17 events queued this week` is a single calm sentence — not a hero-metric template wearing a sentence-case suit.
2. **Empty state diagnoses the cause.** Nine-branch `diagnoseEmpty` writes a headline + nudge for each combination of active filters. "Nothing in Free Food this weekend matches "queer events"" is dramatically more useful than "No results found."
3. **Time-as-anchor card design.** Mono digit + small AM/PM in a left-edge time column gives the feed a typographic skeleton. Twenty cards stacked still feel scannable.

## Priority Issues

**[P1] Mobile touch targets below the project's own 44×44 rule** — multiple sites
- Why it matters: PRODUCT.md commits to "Touch targets ≥44×44px" and mobile-first. The sticky bar Filter button (`EventsFeedColumn.tsx:172`) is `min-h-9` = 36px. Mobile sheet close (`EventsMobileFilterSheet.tsx:151`) is `h-9 w-9`. Sheet submit (`:213`) is `min-h-10` = 40px. Day-window pills in sheet (`EventDayWindowFilter.tsx:13`) are `min-h-9`. Calendar day cells (`EventsMiniCalendar.tsx:111`) are `h-9 w-9`. Month nav arrows (`:62, :70`) are `h-7 w-7` = 28×28. The surface PRODUCT.md commits to most explicitly has the smallest targets.
- Fix: Bump to `min-h-11` (44px) on the Filter button, sheet submit, day-window pills, and close. Calendar day cells `h-11 w-11` fit a 7-col grid inside the sheet's panel (44×7=308 + gap).
- Suggested command: `/impeccable adapt` or `/impeccable harden`.

**[P2] Active filters are not enumerable or individually removable** — `EventsFeedColumn.tsx:228–246`
- Why it matters: "Clear" link is all-or-nothing. A student with Category=Free Food + Window=Weekend + Query="diwali" can't drop just the query. Heuristic 6 caps at 3 because the user has to scan three different UI regions to inventory their own filters.
- Fix: Render a single horizontal row of removable chips above the feed when any filter is active. "Free Food ×" / "This week ×" / `"diwali"` ×. Hairline divider below, no card chrome.
- Suggested command: `/impeccable craft` for the chip-bar component, or `/impeccable shape` first.

**[P2] DESIGN.md is out of sync with the new card design** — doctrine drift
- Why it matters: DESIGN.md documents the colored category rail as "the only sanctioned use of a colored side-stripe pattern" and explains it lets a student "parse twenty cards in two seconds by hue alone." Commit `6e38d8e` removed it. The doc still says it exists. Future contributors will either re-introduce the rail or trust the doc over the code. Scannability-by-category was an explicit goal; cards now signal category only via plain text in the meta row.
- Fix: Decide. Path A — removal was intentional; update DESIGN.md, remove the Category Rail section, replace with a "Time-Anchor Card" section explicitly noting category is now meta-text only. Path B — restore a category signal at lower cost (6px colored leading dot before the title, matching mini-calendar dot palette).
- Suggested command: `/impeccable document` for path A; `/impeccable colorize` or `/impeccable typeset` for path B.

**[P3] Mini-calendar dot encoding has no legend** — `EventsMiniCalendar.tsx:129–143`
- Why it matters: Each day cell renders up to three category-colored dots. The encoding is clever but a first-time visitor has no way to learn it. The day-cell `aria-label` is just "Jump to 2026-05-25" — does not announce categories. Screen reader users get nothing.
- Fix: (a) Extend `aria-label` to include category names: "Jump to May 25, 3 events: Free Food, Social, Academic." Zero visual cost. (b) Add a one-line legend strip below the calendar before the "When" divider.
- Suggested command: `/impeccable clarify`.

**[P3] No `/` or `⌘K` keyboard shortcut for search** — unchanged from prior run
- Why it matters: For Alex (3×/week user), Tab has to traverse the entire masthead and rail before reaching search. `/` is universal for "focus search." Keyboard-only — no visible UI cost.
- Fix: Global keydown listener in `EventsFeedColumn`. If `e.key === "/"` and target is not already an input/textarea/contenteditable, focus `#event-search`. Bonus: Esc while focused clears the query.
- Suggested command: `/impeccable harden`.

## Persona Red Flags

**Alex (Power User)** — student who checks Hub 3×/week:
- URL state now works — they can bookmark `/events?cat=free_food&when=weekend`. ✅ Biggest gap last run; fixed.
- Still no keyboard shortcut to focus search.
- Active filters can't be partially undone — re-picking the filter set after one filter is wrong is annoyance friction.

**Jordan (First-Timer)** — student who landed from an Instagram story link:
- Dateline orients them. ✅
- Mini-calendar dots look like decorative pixels; no legend means Jordan never learns the encoding.
- The "Free" pill is recognizable, but plain "Social / Academic / Career" text in the meta row is harder to scan at a glance.

**UCR undergrad on phone between classes** (project-specific):
- Sticky filter bar's mobile-only Filter button is `min-h-9` = 36px. Below the 44×44 rule. The single most-used mobile entry point.
- Inside the sheet, day-window pills are `min-h-9` and "Show N events" submit is `min-h-10`. Three taps in the sheet all use sub-spec targets.
- Mini-calendar in the sheet has 36×36 day cells.
- The dateline reflects the unfiltered week count even when filters are active. Filtering to Weekend still shows "17 events queued this week."

## Minor Observations

- Dateline (`EventsFeedColumn.tsx:153–157`) shows the unfiltered week count even when filters are active. When a day window is active, swap to `windowPhraseFor(dayWindow)` in the dateline.
- Search input has no clear-button. A small `×` at the right end (visible only when query is non-empty) is the standard affordance.
- Mobile Filter button + active-count badge use `gap-1.5`. The mono 10px badge sits flush right of "Filter." `gap-2` would let the badge read as a separate atom.
- `min-h-14` wrapper around the "More below" sentinel is generous. Consider collapsing to `min-h-10` when not loading.
- `daySections.map(... mb-10)` — 40px between day sections. On mobile this could tighten to `mb-7`.
- Lowercase month + lowercase day-initials + sentence-case "Today" eyebrow are now all consistent. Editorial register is committed.
- Mobile sheet animation: `from { opacity: 0.5 }` means the sheet flashes in half-transparent. `opacity: 0 → 1` paired with the translateY usually reads cleaner.
- `EventDayWindowFilter` rail pills `min-h-8` (32px) are defensible on desktop with a mouse but the sheet variant at `min-h-9` is too small for a thumb.
- Mini-calendar "Today" button (`:53`) is text-only `h-7` next to `h-7 w-7` arrows. Most-likely-used affordance is the hardest to hit.

## Questions to Consider

- What if the dateline reflected the active window? ("This weekend · 4 events queued" when weekend is selected.)
- What if removing the category rail was right, but a 6px leading dot restored the category-scanning signal without the heavy stripe?
- What if `/` focused search and `Esc` cleared it — two shortcuts, no visible affordance, real lift for Alex?
- What if every active filter rendered as a removable chip above the feed — would users actually use it, or is "Clear all" sufficient?
- What if the mini-calendar dots had a tiny legend strip or richer aria-labels — would non-power-users discover the per-day category encoding?
