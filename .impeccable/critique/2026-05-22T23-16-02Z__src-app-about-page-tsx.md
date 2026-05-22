---
target: about page
total_score: 30
p0_count: 0
p1_count: 2
timestamp: 2026-05-22T23-16-02Z
slug: src-app-about-page-tsx
---
# About Page Critique

**Target:** `src/app/about/page.tsx` (+ `src/components/about/AboutFaq.tsx`)  
**Date:** 2026-05-22

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Static page; no broken states. Accordion expand state depends on component (verify focus ring on trigger). |
| 2 | Match System / Real World | 3 | Strong UCR voice; omits HighlanderLink despite PRODUCT/README listing it as a source. |
| 3 | User Control and Freedom | 4 | Clear exits via masthead, external links, FAQ. No traps. |
| 4 | Consistency and Standards | 3 | Matches Hub tokens; weaker than homepage editorial voice (no dateline, no marquee). |
| 5 | Error Prevention | 3 | n/a for forms; copy proactively mentions OCR mistakes. |
| 6 | Recognition Rather Than Recall | 3 | FAQ aids recall; repeated facts (6h refresh, DM handle) force memory anyway. |
| 7 | Flexibility and Efficiency | 2 | No skip links, no section nav, long scroll for power users. |
| 8 | Aesthetic and Minimalist Design | 2 | Opener is tight; mid-page repeats same section grammar and twin 3-up card grids. |
| 9 | Error Recovery | 3 | "Report wrong event" path exists but only via Instagram DM, not linked. |
| 10 | Help and Documentation | 4 | Page *is* the help surface; FAQ is task-focused. |
| **Total** | | **30/40** | **Good** |

## Anti-Patterns Verdict

**LLM assessment:** Not full AI-slop, but fails the project's own anti-references. Two `md:grid-cols-3` card grids (Principles + Get involved) match the "identical icon-heading-text card grids" pattern PRODUCT.md bans. Repeated `text-[13px] text-muted` section eyebrows (6×) read as scaffolding, not a named brand system. Structural rhyme ("Three sources…", "Three ways in…", three principles) feels template-composed. Homepage earns "Quad" personality via FlyerMarquee and feature visuals; About is text-only and loses bulletin warmth.

**Deterministic scan:** Unavailable (`detect.mjs`: bundled detector not found).

**Visual overlays:** Not run (no browser injection in this session).

## Overall Impression

The opener is the best thing on the page: specific problem ("ten different feeds"), concrete UCR examples, strong display type. After that, the page flattens into a long, same-shaped scroll that reads like a well-written FAQ site, not a curated campus bulletin. Biggest opportunity: break the twin card-grid rhythm, add one visual proof of the product (marquee, source diagram, or sample flyer row), and fix source accuracy (HighlanderLink).

## What's Working

1. **Hero narrative** — Problem-first H1 and body copy match "warm, curated, quick" and "could only exist for UCR."
2. **Sources list** — Divided list with colored dots is scannable and avoids nested cards; better than the card sections.
3. **FAQ accordion** — Task-oriented questions; `AboutFaq` uses proper focus classes and readable trigger type.

## Priority Issues

### [P1] Twin identical three-up card grids
- **What:** Principles (lines 107–125) and Get involved (248–323) use the same `rounded-xl border … p-6` card in a 3-column grid.
- **Why:** PRODUCT anti-reference explicitly rejects this; users experience déjà vu mid-scroll.
- **Fix:** Keep one grid max; convert Principles to a hairline row list or single horizontal strip; differentiate Get involved with asymmetric layout or primary/secondary CTA hierarchy.
- **Suggested command:** `impeccable layout about page`

### [P1] Incomplete / inaccurate source story
- **What:** SOURCES lists Instagram, events.ucr.edu, manual only; PRODUCT and pipeline include HighlanderLink.
- **Why:** Club officers and skeptics (Riley) will notice omission; undermines "we gather what clubs already post."
- **Fix:** Add fourth source or merge into copy; align with README/pipeline.
- **Suggested command:** `impeccable clarify about page sources section`

### [P2] Section grammar monotony
- **What:** Six sections share eyebrow + `mt-3` H2 + body pattern; vertical padding clusters at `py-20`/`py-28`.
- **Why:** Cognitive load rises; nothing signals "this section matters more."
- **Fix:** Vary rhythm: one full-bleed band, one two-column without cards, tighten FAQ spacing vs HBI block.
- **Suggested command:** `impeccable layout about page`

### [P2] Copy repetition across folds
- **What:** "Every six hours," "mistakes happen," "DM @hbi.ucr," "within a day" appear 2–3× each.
- **Why:** Violates Impeccable copy law ("every word earns its place"); feels padded for length.
- **Fix:** State each fact once in Sources or FAQ; link from other sections.
- **Suggested command:** `impeccable distill about page`

### [P2] No visual proof of the bulletin
- **What:** Text-only after opener; homepage has `FlyerMarquee` and feature mockups.
- **Why:** About should build trust in aggregation; students scan visually per PRODUCT.
- **Fix:** Reuse marquee strip, 3-tile flyer sample, or simple source-flow diagram (not another card grid).
- **Suggested command:** `impeccable delight about page` or `impeccable layout about page`

## Persona Red Flags

**Jordan (First-Timer):** "Rotation" and "we read the image" without an example flyer; three Get-involved cards look equally important; no inline link for "report wrong event" (FAQ says DM only).

**Casey (Mobile):** Long scroll before FAQ; Principles cards add height early; primary actions in cards use `mt-auto` (good) but page lacks sticky "Submit event" shortcut.

**Riley (Stress Tester):** HighlanderLink missing vs product claims; duplicate timelines (6h auto vs "within a day" manual) may read as contradictory without one timeline block.

**Maya (Student scanner, project-specific):** Strong opener, then wall of similar sections; no quick path back to `/events`; may bounce before FAQ.

**Chris (Club officer, project-specific):** Submit CTA buried in third of Get involved grid; Instagram DM path for org calendar duplicates FAQ without deep link.

## Minor Observations

- HBI logo uses `alt=""` + `aria-hidden` in a content-heavy team block; prefer meaningful alt or decorative-only with heading carrying name.
- Numbered kickers `01`/`02`/`03` in Principles echo SaaS feature grids; consider dropping numbers or using mono dateline style from homepage.
- `hover:text-white` on icon buttons uses pure white (DESIGN.md discourages new pure #fff).
- Register tension: PRODUCT.md says `product` register; About behaves like brand/marketing long-form.

## Questions to Consider

- What if only **one** section used cards, and the rest used lists and hairlines?
- Does Principles need to exist, or could three bullets live in the opener column?
- What would make a student **feel** the bulletin in 5 seconds without reading 800 words?
