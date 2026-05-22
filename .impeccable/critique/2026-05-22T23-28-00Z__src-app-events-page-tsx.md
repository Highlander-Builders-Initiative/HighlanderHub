---
target: events page
total_score: 26
p0_count: 0
p1_count: 2
timestamp: 2026-05-22T23-28-00Z
slug: src-app-events-page-tsx
---
# Events Page Critique

**Target:** `src/app/events/page.tsx` (+ `src/components/events/EventsBrowser.tsx`, `EventCard.tsx`)  
**Date:** 2026-05-22

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Results label (`resultsLabel`) and active filter count update reactively, but loading states are small and lack visual weight. |
| 2 | Match System / Real World | 4 | Speaks UC Riverside campus lingo naturally ("Free Food", "Clubs", "Sports"). Contextualizes UCR rhythm. |
| 3 | User Control and Freedom | 3 | Excellent scroll restoration state recovery (`restoreSavedSpot`). However, there is no way to clear individual filters without manually clearing everything. |
| 4 | Consistency and Standards | 2 | Major deviations from `DESIGN.md` tokens (card title font size is `text-[16px]` vs `18px`, active chips are black instead of using category colors, and the submit button has background-inversion hovers). |
| 5 | Error Prevention | 3 | Filter boundary cases are prevented through static selections and standard text inputs. |
| 6 | Recognition Rather Than Recall | 3 | The sticky filter bar pins controls to the top of the viewport nicely, but search lacks autocomplete or active filter indicators. |
| 7 | Flexibility and Efficiency | 2 | Excellent session recovery, but lacks keyboard accelerators for desktop power users. |
| 8 | Aesthetic and Minimalist Design | 2 | The three-column stats grid in the header ("Loaded", "This week", "Free food") is a classic SaaS metric cliché (which is an absolute ban under `DESIGN.md`). |
| 9 | Error Recovery | 3 | Clear "Retry" patterns when infinite scroll page requests fail, keeping user context intact. |
| 10 | Help and Documentation | 1 | No contextual tooltips, empty-state guidance, or quick-start information for new students or officers submitting events. |
| **Total** | | **26/40** | **Acceptable** |

## Anti-Patterns Verdict

* **LLM Assessment (AI Slop Test)**: 
  * **The SaaS Metric Trap**: The three-column stats grid in the header is a direct violation of the Absolute Ban on the *SaaS hero-metric template*. It looks like an admin dashboard or YC landing clone rather than a warm, student-curated quad bulletin.
  * **Monochromatic Coldness**: The active filter chips use a rigid, stark `bg-ink text-white` (solid near-black background). This ignores the brand's five-accent category color strategy (Warm Gold, Citrus Coral, Forest Leaf, Clear Sky) and feels highly clinical and mechanical.
  * **Button Hover Background-Shift**: The `SubmitEventCta` component implements an inverse hover which conflicts with the button Primary/Secondary specs in `DESIGN.md` that explicitly prohibit hover background-shifts.
* **Deterministic Scan (Manual Code Audit)**:
  * **Card Title Mismatch**: `EventCard.tsx` uses `text-[16px] sm:text-[17px]` instead of the `1.125rem / 18px` specified in the `Title` typographic hierarchy.
  * **Time Label Size**: `EventCard.tsx` renders the event startsAt time using `text-[13px]` which diverges from the `0.6875–0.75rem / 11–12px` specified for `Numeric/Mono` labels.

## Overall Impression

Highlander Hub has a phenomenal foundation: the typography scale (Bricolage Grotesque display type + Inter body), hairline borders, and advanced scroll restoration make the feed feel premium, fast, and solid. 

However, the events page was held back by **SaaS-cliché visual noise** (the stats header) and a **lack of warm, scannable category colors** in the filter bar. Stripping the mechanical metrics and breathing the category color system into the active chips will immediately elevate this page into a warm, student-curated campus bulletin.

## What's Working

1. **Hairline Aesthetic & Rhythm**: The hairline borders (`border-ink/15`) and 1px translateY hover lift (`.card-hover`) create a very premium, paper-like confidence.
2. **State and Scroll Restoration**: The scroll restoration mechanism is exceptionally robust, allowing students to browse smoothly without losing place.
3. **Clean Micro-Interactions**: The category rail (`w-1` left stripe) on the text-variant event cards is a brilliant, scannable visual cue.

## Priority Issues

* **[P1] SaaS-Cliché Metric Block (The Hero-Metric Template)**
  * **Why it matters**: The header's stats column feels transactional, sterile, and looks like a YC-startup metrics block. It clashes with the warm, human tone of a campus bulletin.
  * **Fix**: Replace the metric block with a dynamic, warm editorial summary sentence.
  * **Suggested command**: `distill`

* **[P1] Monochromatic Active Filters (Category Color Mismatch)**
  * **Why it matters**: Active category chips currently render as a cold, monochromatic black, neglecting your brand’s beautiful category colors.
  * **Fix**: Update active states to apply category background and text colors dynamically matching the `DESIGN.md` palette.
  * **Suggested command**: `colorize`

* **[P2] Button Hover Background Shift (Spec Mismatch)**
  * **Why it matters**: The `SubmitEventCta` uses a background-inverting hover, violating the button specs in `DESIGN.md`.
  * **Fix**: Conform it to standard Primary Button specs (solid near-black background, simple opacity transition).
  * **Suggested command**: `layout`

* **[P2] EventCard Typographic Scale Mismatches**
  * **Why it matters**: The event card titles are too small (breaking the `18px` specification) and time labels too large (breaking the `11-12px` Mono rule).
  * **Fix**: Apply the correct typographic variable sizes.
  * **Suggested command**: `typeset`

## Persona Red Flags

* **Casey (Distracted Mobile User)**:
  * Red Flag: The sticky filter bar + page header takes up massive mobile vertical space. Indistinguishable monochrome active chips make category filtering hard to target or identify at a glance.
* **Jordan (First-Timer)**:
  * Red Flag: Dry database metrics ("Loaded: 42") and a giant stark title don't introduce Highlander Hub as a warm student quad bulletin or guide them.
* **Marcus (UCR Club Officer)**:
  * Red Flag: Marcus sees database load metrics rather than views, active clubs, or highlights showing his organization's event is getting real traction.

## Minor Observations

* **Clear Button Placement**: In `EventsBrowser.tsx`, the "Clear" button wraps to a new line on small viewports, making it hard to tap.
* **Search Box Styling**: The search input has a bottom-border-only treatment but lacks a smooth transition on focus other than the global focus ring.
