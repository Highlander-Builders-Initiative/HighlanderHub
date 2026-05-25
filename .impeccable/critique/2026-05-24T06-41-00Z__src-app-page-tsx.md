---
target: landing page
total_score: 34
p0_count: 0
p1_count: 0
timestamp: 2026-05-24T06-41-00Z
slug: src-app-page-tsx
---
# Design Critique: src/app/page.tsx (Landing Page)

This document contains a comprehensive visual and interactive critique of the Highlander Hub landing page.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 4/4 | Solid dateline colophon showing active dates, HBI links, and active upcoming events; dynamic SSR loading is robust. |
| 2 | Match System / Real World | 4/4 | High-fidelity UCR student terminology ("Free food", "intramurals"). Physical "bulletin wall" metaphor through FlyerMarquee works wonderfully. |
| 3 | User Control and Freedom | 4/4 | Smooth scroll controls on marquee with hover/focus pause. No navigational traps, and reduced-motion preferences are fully honored. |
| 4 | Consistency and Standards | 3/4 | Font usage is highly consistent with Bricolage and IBM Plex Mono, but `HeroLeadEvent` leaks monospace font onto plain-text weekday relative labels (e.g., "Today", "Tomorrow"). |
| 5 | Error Prevention | 4/4 | Marquee fails gracefully on empty state, and events count uses a safe catch fallback to prevent page break. Touch targets conform to ≥44px height. |
| 6 | Recognition Rather Than Recall | 4/4 | Visual discovery cues are clear. Upcoming event cards and flyers are immediately readable, and the main CTA is highly visible. |
| 7 | Flexibility and Efficiency of Use | 3/4 | Speedy prefetching on link hover. No keyboard shortcuts are implemented on the landing page, though duplicate flyers are appropriately hidden. |
| 8 | Aesthetic and Minimalist Design | 4/4 | Exquisite editorial paper-bulletin look. Line lengths are tight, colors are strictly category-rationed, and there are no generic SaaS templates or gradient texts. |
| 9 | Error Recovery | 4/4 | No interactive forms or inputs are present on the landing page, avoiding validation recovery issues. |
| 10 | Help and Documentation | 4/4 | The colophon and editor's notes clearly explain where listings come from, providing transparent contextual expectations. |
| **Total** | | **34/40** | **Good (Solid foundation, address minor leaks)** |

## Anti-Patterns Verdict

*   **LLM Assessment (AI Slop Verdict)**: Clean. This does *not* look like a generic AI or SaaS landing template. It has no SaaS clichés (e.g., "10,000+ events tracked" hero metrics, stock photography grids of diverse people smiling at laptops, or gradient text overlays). The typography leads with strong semibold Bricolage display and the composition feels highly editorial and paper-confident, matching the brand context perfectly.
*   **Deterministic Scan**: Deterministic scan unavailable (bundled detector not found).
*   **Visual Overlays**: No reliable user-visible overlay is available (bundled detector/browser preflight unavailable or run sequential sequential).

## Overall Impression

Highlander Hub's landing page is exceptionally polished and fulfills its creative north star—"The Quad"—by presenting a curated campus paper aesthetic. The FlyerMarquee scroll feels alive and the copy is highly tailored to UCR students. The design operates with extreme restrain, utilizing Category Dot accents at ≤10% visual weight. Spacing and rhythm are excellent, and the layout works brilliantly. The main area for refinement lies in micro-typographical consistency and small micro-interaction touches.

## What's Working

1.  **Editorial Personality**: The brand colophon, "Note from the editors," and dateline give the page a distinct publication feel rather than a corporate transactional marketplace.
2.  **FlyerMarquee Wall**: The continuous horizontal marquee acts as a living bulletin wall. The pause-on-hover/focus micro-interaction and sub-pixel carry prevent visual jumping, showing extreme attention to details.
3.  **Strict Accent Rationing**: Color is strictly meaningful and kept in category accents, highlighting details (e.g., green dot for leaf, gold for food) instead of visual clutter.

## Priority Issues

### [P2] Monospace Font Leak on Text Labels
*   **Why it matters**: In `HeroLeadEvent.tsx`, the relative day label (`Today`, `Tomorrow`, or weekday names) is wrapped in the parent `font-mono` class, rendering plain-text words in `IBM Plex Mono`. This violates `DESIGN.md`'s rule reserving monospace purely for numeric and date digits (to avoid the SaaS/dev-tool AI slop look).
*   **Fix**: Move the `font-mono` class to the exact `{time}` span or wrap `{day}` in Bricolage Grotesque to ensure monospace is reserved strictly for numeric values.
*   **Suggested command**: `typeset`

### [P3] HBI Byline Logo Static Hover
*   **Why it matters**: The HBI Byline Link (`HbiLink`) text turns ink on hover, and the logo image has a `transition-transform` class, but there is no actual scale or movement class triggered on hover.
*   **Fix**: Add a subtle `group-hover:scale-105` or `group-hover:translate-y-[-1px]` to the byline logo image to make the micro-interaction feel fully responsive.
*   **Suggested command**: `delight`

## Persona Red Flags

*   **Casey (Distracted Mobile User)**: Casey accesses the page while walking between classes on UCR campus. The layout is highly thumb-optimized: the primary "Browse events" CTA is massive (`min-h-12`) and in the center. Tap targets are generous. Marquee auto-scrolling pauses instantly when thumb-held. **Zero red flags found for Casey.**
*   **Jordan (First-Timer)**: Jordan is looking for free food on campus. Jordan immediately recognizes the "Free food" copy in the hero paragraph, sees the UCR colophon, and understands the page's purpose within 5 seconds. Exits are clearly labeled. **Zero red flags found for Jordan.**
*   **Maya (UCR Undergrad - Project Specific)**: Maya is distracted, looking to scan flyers quickly on her phone. She opens the page and is wowed by the "Now on the wall" FlyerMarquee, seeing vibrant event flyers at a glance. However, she notices that in the "Coming up" lead card, the weekday label ("Today" or "Monday") reads in a slightly blocky monospace style, which looks a bit like a developer terminal instead of an editorial paper.
