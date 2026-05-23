---
target: landing page
total_score: 24
p0_count: 1
p1_count: 2
timestamp: 2026-05-23T00-31-40Z
slug: src-app-page-tsx
---
# Critique — Landing page (`src/app/page.tsx`)

The landing operates under the **brand register** (a marketing/landing surface, not the product app it leads into). DESIGN.md commits the system to an editorial-bulletin aesthetic, which is treated as identity-preservation: the lane is not in question, but where the execution is timid, generic, or pose over voice is.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Dateline + "N events this week" is good; nothing else changes state |
| 2 | Match System / Real World | 3 | "The wall" metaphor lands; "Every UCR event, one app" is system-speak that fights it |
| 3 | User Control and Freedom | 3 | Two CTAs + nav; marquee pauses on hover/focus. Submit is equalized next to Browse |
| 4 | Consistency and Standards | 4 | System is well-codified and the page honors it |
| 5 | Error Prevention | n/a | Landing has no input state |
| 6 | Recognition Rather Than Recall | 3 | Flyer strip is recognition-first. "Now on the wall" eyebrow doesn't earn its place |
| 7 | Flexibility and Efficiency | 2 | No way to jump into a category from the hero; one-path discovery |
| 8 | Aesthetic and Minimalist Design | 3 | Tightly composed, but minimalist-by-default on a brand surface |
| 9 | Error Recovery | n/a | No errors on landing |
| 10 | Help and Documentation | 3 | Hero copy + About link in masthead |
| **Total** | | **~24/32 scored** | Competent restrained; under the brand bar |

## Anti-Patterns Verdict

**LLM assessment.** Does not scream "AI made that" — the system has real opinions held consistently. But it lands in the **editorial-typographic** lane brand.md flags as currently saturated: hairline rules, mono micro-labels, small dateline, restrained monochrome, a centered-stack hero pattern. The voice is "campus paper" in label-strings but the layout shape underneath is the YC landing-template grid. Costume-on-template.

**Deterministic scan.** Bundled detector engine is missing from this install. Manual scan against absolute bans turned up no violations: no side-stripe borders, no gradient text, no nested cards, no decorative glass outside sanctioned uses, no em dashes, no `#000`/`#fff` in component code, no animating layout properties, no bounce/elastic motion.

**Visual overlays.** No browser automation available; no live overlay shown.

## Overall Impression

Well-mannered, technically careful, politely on-brand. Also forgettable. The five-second test fails not on clarity but on **distinctiveness**. The single biggest opportunity: commit the brand surface to color and image the way the brand register actually permits. This page is following product-register color discipline on a surface where Committed / Full Palette / Drenched are the correct registers.

## What's Working

- **The dateline + week-count micro-line.** "May 22, 2026 · 14 events this week" is content-as-orientation, dated, finite, edited. Carries more brand than the headline does.
- **The flyer marquee, mechanically.** Sub-pixel carry, reduced-motion respect, focus-pause, silent duplicates kept out of the a11y tree — the component itself is excellent. The framing around it is the problem.
- **The system is consistent.** Hairlines, ink-tinted neutrals, three-font discipline, focus rings, motion easing — DESIGN.md is genuinely lived.

## Priority Issues

### [P0] The hero headline collapses into "one app"
**Why it matters.** "Every UCR event, one app." — the second half is the genericized SaaS finish. PRODUCT.md principle #5 says "Could only exist for UCR." "One app" could be a delivery service, transit tracker, workout log.
**Fix.** Replace the second clause with something that names what *this page* is. Candidates: "Every UCR event, **one wall.**" / "Every UCR event, **one page.**" / restructure entirely ("**This week, at UCR.**" with the dateline absorbed as kicker).
**Suggested command.** `/impeccable clarify landing page`

### [P1] The Features section is a three-card grid with a fake calendar in it
**Why it matters.** One lead card + two supporting cards = literal YC homepage Features template; "identical icon-heading-text card grids" is in PRODUCT.md anti-references. The calendar card ships a hand-coded fake calendar with fake category dots; for a brand that prizes "curated, not infinite" and "honest, not padded," using a faked screenshot is a credibility miss.
**Fix.** Either (a) drop Features entirely — marquee + tighter CTA already do the work; or (b) replace with one full-bleed editorial moment: a real calendar from real events, a "Free food this week" list rendered as a typographic broadsheet, or a quote from a club officer.
**Suggested command.** `/impeccable distill landing page` then `/impeccable bolder`.

### [P1] The brand surface is following product-register color discipline
**Why it matters.** Largest under-commitment. brand.md: brand surfaces have permission for Committed / Full Palette / Drenched strategies. Current landing is functionally monochrome with one polite gold tint and a few calendar dots. The five category hues exist in the system and they are the most UCR-specific element owned — and they are absent from the hero, marquee, and CTA band.
**Fix.** Name a real reference, then pick one of two directions:
- **Drenched-gold hero.** Above-the-fold as a warm-gold field; ink on gold. Reads as a printed flyer.
- **Full-palette categorical hero.** Subhead's category words each render in their own paired text color from the system. The hero teaches the color system in the first glance.
**Suggested command.** `/impeccable colorize landing page`

### [P2] "Submit an event" is equalized next to "Browse events"
**Why it matters.** Design Principle #4: "Discovery is the front door; submission is a side door." They are side-by-side at the same `min-h-12` tap height. On a 375px phone, the underline-link sits one mis-tap away from the primary CTA.
**Fix.** Drop "Submit an event" from the hero. Add it to the masthead nav (currently only Events + About). Footer already carries it. Hero is single-CTA.
**Suggested command.** `/impeccable shape landing page`

### [P2] HBI byline + rotating-logo hover is twee
**Why it matters.** The hover micro-rotation on the logo (`group-hover:-rotate-6`) is a designer-flourish on a non-interactive attribution. The project's stored guidance rejects vibe-coded reflexes (live dots, pulsing chips) on the landing; this is a cousin.
**Fix.** Drop the rotation. Treat the byline either as a quiet line in the footer only, or as a real editorial credit ("Edited weekly by Highlander Builders Initiative" — claims the editorial labor the bulletin metaphor implies).
**Suggested command.** `/impeccable quieter landing page` for the byline; `/impeccable clarify` for the copy.

## Persona Red Flags

**Maya (sophomore, on a phone between classes — primary persona).** Sees dateline (good), reads "Every UCR event, one app" (registers as marketing), reads subhead (better), and below fold sees small flyer thumbnails. She has to scroll past the hero to find "Free food this week" — the killer feature, buried in section 2. **Free food this week belongs in the hero.**

**Diego (club officer submitting).** Sees "Submit" in hero — relief. Clicks; it works. But landing did nothing to make him feel the host experience is taken seriously: no language addressed to clubs, no preview of what his event will look like once posted.

**Alex (returning user).** No category shortcut. Two clicks (Browse → /events → filter) where one would do. The category palette is the brand's defining content axis and absent from the hero entry.

## Minor Observations

- **"Now on the wall" caption.** Either earns a full editorial section title ("This week on the wall", display type, hairline beneath) or removed. Currently caption-as-apology.
- **"highlander/hub" wordmark.** Lowercase slash-separated wordmark is the developer-tool shape (linear, vercel, notion). Identity-preservation applies; just be aware it reads dev-tool, not campus.
- **The hero hairline above the headline.** Doing nothing structural; spacing alone separates dateline from headline. Remove it.
- **No alt text strategy for flyer images.** `flyerAlt(event)` returns "Flyer for {title}" — bare minimum, misses the warmth promise. brand.md: "alt text is part of the voice."
- **Footer "Not affiliated with UC Riverside."** Quietly correct, properly placed. Keep.

## Questions to Consider

- What if "Free food this week" *were* the hero, and the marquee were the secondary section?
- What's the single thing a student sees in the first 1.5 seconds, and is that thing UCR-specific or app-shaped?
- If you removed the Features section entirely, what would the page lose that the user needs?
- What does a confident, hue-committed version look like? (Pick a real reference; don't drift back to neutral.)
- Is the editorial-bulletin metaphor doing real work, or is it design vocabulary in label-strings while the underlying layout stays SaaS?
