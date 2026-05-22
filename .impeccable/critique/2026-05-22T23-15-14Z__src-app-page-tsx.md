---
target: Homepage (/)
total_score: 27
p0_count: 0
p1_count: 3
timestamp: 2026-05-22T23-15-14Z
slug: src-app-page-tsx
---
# Critique: Homepage (`src/app/page.tsx`)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Dateline + week count is a strong "what's fresh" signal; marquee lacks scroll-position cue |
| 2 | Match System / Real World | 3 | "Now on the wall" lands; hero "one app" is product-speak, off-voice |
| 3 | User Control and Freedom | 3 | n/a for landing — marquee pause-on-hover is correct |
| 4 | Consistency and Standards | 3 | Hardcoded hex (`#8a6300`, `#1f6f4e`) inside `LandingSections.tsx` bypasses DESIGN.md tokens |
| 5 | Error Prevention | 3 | n/a |
| 6 | Recognition Rather Than Recall | 3 | Sticky masthead always visible; marquee tiles hide category, so users can't recognize event type at a glance |
| 7 | Flexibility and Efficiency | 2 | One path off the homepage; no search, no shortcuts |
| 8 | Aesthetic and Minimalist Design | 2 | Features section is a textbook generic-SaaS card grid; FinalCTA carries three competing actions |
| 9 | Error Recovery | 3 | n/a |
| 10 | Help and Documentation | 2 | Features section tries to be inline help, but arrives after the wall and only via scroll |
| **Total** | | **27/40** | **Acceptable — solid bones, two sections off-voice** |

## Anti-Patterns Verdict

**LLM assessment.** The page splits in two. The hero and FlyerMarquee read as a real campus thing — dateline, "Now on the wall," HBI byline with a tiny -6deg logo wink, real flyers crawling left. That section honors the "edited bulletin" voice DESIGN.md describes.

The Features section and FinalCTA reverse course: numbered eyebrow + headline + body + mocked-UI card, repeated three times, followed by "Ready when you are" eyebrow + headline + button cluster. That is a generic SaaS landing template wearing the project's typography. PRODUCT.md explicitly lists "identical icon-heading-text card grids" as an anti-reference; the visuals being mocked screenshots instead of icons softens it but does not change the structure. The hero copy "Every UCR event, one app." is value-prop tag, not campus voice — closer to a YC pitch than a student-paper masthead.

The site's own thesis (color carries meaning, hue is for category) does not appear anywhere on the homepage. Marquee tiles show date + title only. A first-time visitor sees no evidence that this product is organized by category at all until they're three scrolls deep into the Features mocks.

**Deterministic scan.** `detect.mjs` exits with `Error: bundled detector not found` — the detector engine (`detect-antipatterns.mjs`) was not shipped with this skill install. Manual scan against the parent skill's absolute-bans list: no side-stripe borders outside the sanctioned category rail, no gradient text, no glassmorphism outside the three sanctioned surfaces (masthead is the only one on this page), no hero-metric template. But the Features grid does fit the identical-card-grid pattern.

**Visual overlays.** No browser automation in session. No live overlay generated.

## Overall Impression

The first screen is doing real work — the FlyerMarquee is the kind of "could only exist for UCR" idea PRODUCT.md asks for, and the editorial dateline gives the page a voice. Then the page reverts to a marketing template for two more sections and undoes most of that goodwill. The single biggest opportunity is to keep the editorial register all the way down: kill or redesign the Features section, trim the FinalCTA, and put the brand's category-color discipline onto the FlyerMarquee where students can actually use it to scan.

## What's Working

- **The FlyerMarquee concept.** Auto-scrolling, pause-on-hover/focus, sub-pixel carry, reduced-motion fallback, decorative duplicates pulled out of the a11y tree (`tabIndex={-1}`, `aria-hidden`). Engineering matches the metaphor.
- **The dateline.** `Tue, May 21 · 14 events this week` in IBM Plex Mono at 11px is exactly the campus-paper colophon DESIGN.md describes. It doubles as a freshness signal and a soft system-status indicator — one line earning three jobs.
- **CTA hierarchy in the hero.** Solid ink "Browse events" + underlined "Submit an event" enforces the "discovery is the front door, submission is a side door" principle visually, not just structurally.

## Priority Issues

**[P1] FlyerMarquee tiles hide category — the wall fails the "scannable" promise.**
*Why it matters.* DESIGN.md says hue carries meaning and "lets a student parse twenty cards in two seconds by hue alone." PRODUCT.md says "scannable beats searchable" and that students give the site five seconds. The wall is the five-second surface and it shows zero category signal. A student looking for free food has to open each tile to find out.
*Fix.* Add the documented overlay-variant Category Pill (`bg-white/15 backdrop-blur-sm` + matched text color) to `FlyerTile` at `size="medium"`. Position bottom-left under the date or top-right corner; either is consistent with the existing image-variant EventCard.
*Suggested command.* `/impeccable colorize`.

**[P1] Hero headline is off-voice — trades campus warmth for value-prop pitch.**
*Why it matters.* PRODUCT.md is explicit: "warm, never corporate," "if a sentence could appear on a B2B SaaS landing, rewrite it." "Every UCR event, one app." is precisely that sentence. It sits one line above a beautifully voiced dateline, so the mismatch is visible in the same screen.
*Fix.* Rewrite with the bulletin voice. Options: "What's on this week." / "Bagels, club nights, career fairs." / "What's actually happening at UCR." Keep the two-line scale + muted second line; change the words.
*Suggested command.* `/impeccable clarify`.

**[P1] Features section is the generic-SaaS template the brand explicitly rejects.**
*Why it matters.* Three identical numbered cards with mocked UIs is the structural anti-reference. Numbered eyebrows ("01", "02", "03") imply a sequence that isn't there. The section also competes with the FlyerMarquee — it's explaining something the marquee is already demonstrating.
*Fix.* Three real options, pick one:
1. Editorial layout: two asymmetric strokes (a "Filter what matters" left-aligned spread with a real screenshot, a "Free-food toggle" right-aligned with the gold pill in actual context). No numbered eyebrows, no cards.
2. Marginalia: full-width section header, three short notes set as marginalia/sidebars on a body-prose column.
3. Delete it. The FlyerMarquee already proves the product works.
*Suggested command.* `/impeccable distill`, then `/impeccable layout` on whatever survives.

**[P2] FinalCTA carries three competing actions of equal weight.**
*Why it matters.* The hero established a 1-primary-1-secondary CTA pattern. FinalCTA breaks it: Browse (ink button) + Submit (underline) + About the project (underline). "About the project" lives in the masthead nav and twice in the footer; it does not need a third entry point here. The eyebrow "Ready when you are" is filler — the SaaS landing eyebrow DESIGN.md warns against.
*Fix.* Drop the About link. Drop the "Ready when you are" eyebrow. Let "Stop missing events." carry the surface alone with Browse + Submit beneath it.
*Suggested command.* `/impeccable quieter`.

**[P3] Hardcoded hex in `LandingSections.tsx` (`text-[#8a6300]`, `text-[#1f6f4e]`) bypasses the design system.**
*Why it matters.* DESIGN.md's Meaning-Carrying Rule requires category color from documented pairs. Inline hex hides intent from grep and from future Tailwind changes.
*Fix.* Extend `tailwind.config.ts` with `gold-deep`, `leaf-deep`, `coral-deep`, `sky-deep` (matching the four documented dark-text pairings), then use `text-gold-deep` etc.
*Suggested command.* `/impeccable extract`.

## Persona Red Flags

**Casey (Distracted Mobile User)** — Primary persona per PRODUCT.md. Hero stacks dateline + headline + supporting paragraph + 2 CTAs vertically; on a 380px viewport the FlyerMarquee doesn't appear until well below the fold. Casey's first glance is "branded landing," not "what's happening." On the marquee itself, autoscroll competing with swipe gestures feels slippery on iOS — pause-on-pointer-enter helps a mouse user, but a touch user pauses by *starting* a swipe, which is the same gesture as scrolling. Browse/Submit CTAs sit in a 5-gap row which on a tight screen places them within tap-conflict distance for a thumb.

**Jordan (First-Timer)** — Brand-new student lands on the page. The FlyerMarquee is intuitive (things move, you can swipe), but Jordan can't tell at a glance which events are clubs vs. free food vs. career fairs. Jordan has to scroll to the Features section to learn categories exist, then scroll back up — by which point the marquee has rotated. Recognition happens too late and in the wrong order. "About the project" reads more cautious than the rest of the page — Jordan may read it as "is this a beta? not the real campus site?"

**Custom — Maya (UCR student between classes):** Per PRODUCT.md, the primary user. Opens the site for five seconds while walking. Sees: huge dateline, huge headline, paragraph she doesn't read, two buttons. Has to choose Browse vs. Submit before she sees any actual events. The FlyerMarquee — the thing she came for — is two scrolls down. The five-second test fails by structure: she sees marketing before she sees the bulletin.

## Minor Observations

- "Built by Highlander Builders Initiative" appears three times (hero byline, footer brand block, footer connect block). One mention is warmth; three is repetition.
- `Masthead` mobile nav uses `text-black` (lines 91, 106) instead of `text-ink`. Trivial, but it's the project's only pure-black reference and breaks the tinted-neutral rule.
- Two `.hairline` rules sit close together in the hero (one under the dateline, one above the marquee). Two hairlines in one section flatten the rhythm; let the type spacing carry the upper division.
- Hero `<h1>` uses inline arbitrary clamp values (`text-[38px] sm:text-[56px] md:text-[64px] lg:text-[72px]`) where DESIGN.md defines `display: clamp(2.25rem, 5.5vw, 4.5rem)` as a token. Drifts from the spec on the responsive endpoints.
- Footer "Built by HBI" link targets `/about`; hero HBI link targets `instagram.com/hbi.ucr`. Two different destinations for the same string of text.
- `FlyerMarquee` has no `aria-label` or `role="region"`. A screen reader hears a list of links with no context.

## Questions to Consider

- What if the FlyerMarquee opened the page and the hero text sat *under* it, like a colophon under a masthead photo? The page would prove its concept before it pitched it.
- The brand voice promises "occasionally opinionated." Where on this page does an actual editorial opinion show up? An "Editor's pick" tile in the marquee, or a one-line "Don't miss" callout, would honor that promise.
- Does the Features section need to exist at all if the FlyerMarquee is doing its job?
- The week count ("14 events this week") is a quiet, lovely signal. Could it grow into something more diary-like — "Quiet week" / "Packed week" / "Finals week, mostly study breaks" — without crossing into cute?
