---
name: Highlander Hub
description: A scannable campus and club events bulletin for UC Riverside.
colors:
  canvas: "#ffffff"
  surface: "#fafafa"
  line: "#e7e7e9"
  ink: "#0f1115"
  muted: "#6b7280"
  deep-navy: "#1e3a8a"
  warm-gold: "#f5b400"
  citrus-coral: "#ef5d4f"
  forest-leaf: "#2f9e6f"
  clear-sky: "#3b82f6"
  deep-leaf: "#1f6f4e"
  deep-coral: "#b33a30"
  deep-sky: "#1d5fbf"
  deep-gold: "#8a6300"
typography:
  display:
    fontFamily: "Bricolage Grotesque, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(2.25rem, 5.5vw, 4.5rem)"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Bricolage Grotesque, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Bricolage Grotesque, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  meta:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
  numeric:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
    fontSize: "0.6875rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.04em"
rounded:
  sm: "4px"
  md: "8px"
  lg: "12px"
  xl: "16px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.canvas}"
    rounded: "{rounded.md}"
    padding: "12px 24px"
  button-primary-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.canvas}"
  card:
    backgroundColor: "{colors.canvas}"
    rounded: "{rounded.xl}"
    padding: "16px"
  card-hover:
    backgroundColor: "{colors.canvas}"
  badge-pill:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.full}"
    padding: "2px 10px"
  input-text:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "10px 12px"
  masthead:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
---

# Design System: Highlander Hub

## 1. Overview

**Creative North Star: "The Quad"**

Highlander Hub is the screen-side stand-in for the physical UCR campus: many voices, edited gathering, a place rather than a tool. The interface is a place a student passes through, glances at, and leaves having seen something they wouldn't have seen otherwise. It is not a search engine, not a feed, not a marketplace. It is a quad with a bulletin in it.

The system reads as **edited and paper-confident**: display type does the work, chrome stays hairline-thin, and the page is built to be skimmed in five seconds before it asks for any commitment. Color is tightly rationed and meaningful (the category palette is the only place hue lives); everything else sits in tinted neutrals. The voice is warm, never corporate; specific to UCR, never genericized. The brand personality from PRODUCT.md, **warm, curated, quick**, is enforced visually by a small set of doctrine: tinted neutrals, one display family, one body family, one mono, and a Restrained color strategy that holds accent usage well below 10% of any surface.

The system explicitly rejects three aesthetic families called out as anti-references in PRODUCT.md: **generic SaaS landing** (hero-metric templates, identical card grids, gradient text), **university .edu CMS** (institutional navy soup, brochure density, slow chrome), and **Eventbrite / Meetup transactional** (ad clutter, RSVP-button soup, marketplace dating). If a screen could be confused for any of those at a glance, it has failed.

**Key Characteristics:**
- Hairline-bordered surfaces; depth via 1px lifts, not shadow blooms (current state; see Elevation for direction).
- Bricolage Grotesque display + Inter body + IBM Plex Mono labels. No fourth font.
- OKLCH thinking, hex frontmatter; tinted neutrals only, no pure #000.
- Restrained color strategy: category accents at ≤10% of any surface, expressed as tinted backgrounds (`/10`–`/15`) plus a darker matched text color for AA contrast.
- Mobile-first: every layout is designed for a phone first, scaled out.
- Motion is decelerating-only (ease-out-expo), no bounce, no elastic, reduced-motion honored at the root.

## 2. Colors: The Quad Palette

The palette is a wide, tinted-neutral page with five accent hues used **only** as event-category signals. Neutrals carry layout; hues carry meaning.

### Primary

- **Deep Navy** (#1e3a8a): The UCR-leaning accent. Used as the "Club" category color and the optional hover color on the masthead's HBI byline link. Reserved for one role, deliberately rare. Never used as a large background fill.

### Secondary (the category quintet)

These four colors exist as **category signals**, not decoration. Each one has exactly one role: pair the swatch (used at 10–15% opacity for backgrounds) with the matched darker text color for AA contrast.

- **Warm Gold** (#f5b400) paired with **Deep Gold** (#8a6300): "Free Food."
- **Citrus Coral** (#ef5d4f) paired with **Deep Coral** (#b33a30): "Social" and "Arts."
- **Forest Leaf** (#2f9e6f) paired with **Deep Leaf** (#1f6f4e): "Academic" and "Community."
- **Clear Sky** (#3b82f6) paired with **Deep Sky** (#1d5fbf): "Sports."

"Career" reuses **Ink** as its category color (no third neutral is invented).

### Neutral

- **Canvas** (#ffffff): The default page background.
- **Surface** (#fafafa): One tonal step up for sectioned regions, marquee strips, subtle backgrounds.
- **Line** (#e7e7e9): Border / divider / hairline. Used as `border-ink/10` or `border-ink/15` in the codebase.
- **Ink** (#0f1115): Primary text. A near-black with a slight cool tint, never pure #000.
- **Muted** (#6b7280): Secondary text, eyebrow labels, meta information.

### Named Rules

**The One Voice Rule.** Category color appears as a tinted background (`/10` or `/15` opacity), never as a saturated fill behind body content. Total accent coverage on any screen stays at or below 10% of the surface. Saturated category color appears in exactly one place: the 4px category rail on the left edge of `EventCard`.

**The Tinted-Neutral Rule.** No new pure-hex grayscale values. Every neutral tints toward the cool ink hue. If you need a step between `surface` and `line`, derive it from the existing ramp, do not invent a flat gray.

**The Meaning-Carrying Rule.** Hue is for category. If a UI element uses color but is not signaling a category, it is wrong. Promotional accents, decorative gradients, mood-color washes: prohibited.

## 3. Typography

**Display Font:** Bricolage Grotesque (with `ui-sans-serif, system-ui, sans-serif` fallback)
**Body Font:** Inter (with `ui-sans-serif, system-ui, sans-serif` fallback)
**Label / Mono Font:** IBM Plex Mono (with `ui-monospace, monospace` fallback)

**Character:** Bricolage Grotesque is the editorial-display voice: optical-sizing on, slight negative tracking, semibold default. It does the work. Inter sits at 16px / 1.55 line-height for body, a calm reading face that never competes with the display, and at 13px for quiet labels, taglines, and meta strings. IBM Plex Mono is reserved for content that is genuinely numeric (dates, times, location coordinates, identifiers), never decorative caps. The pairing is intentionally student-magazine: a confident headline face over a calm body face, with mono used only where it earns its place.

### Hierarchy

- **Display** (600 weight, `clamp(2.25rem, 5.5vw, 4.5rem)`, line-height 1.0, tracking -0.035em): Hero headlines only. One per page.
- **Headline** (600, 1.75rem / 28px, line-height 1.15, tracking -0.02em): Section openers (Features, FinalCTA, page titles).
- **Title** (600, 1.125rem / 18px, line-height 1.2, tracking -0.015em): Event card titles, card-level headings. Two-line clamp.
- **Body** (400, 1rem / 16px, line-height 1.55): Paragraph text. Cap line length at 65–75ch.
- **Meta** (400, 0.8125rem / 13px, line-height 1.4, normal tracking): Quiet labels above or beside primary content: eyebrows, taglines, summary lines, captions. Inter, sentence case, muted color. No uppercase, no tracking-out.
- **Numeric** (400, 0.6875–0.75rem / 11–12px, line-height 1, light tracking ≤0.06em, sentence case): Dates, times, location strings, identifiers, calendar grid numbers. IBM Plex Mono. Used only where the content is genuinely numeric or coordinate-like, never as decorative label-style.

### Named Rules

**The One-Display Rule.** Bricolage Grotesque is the only display face. Inter is the only body face. IBM Plex Mono is the only mono. No fourth font is added without retiring one of the three.

**The Tracking Rule.** Display type tracks tight (-0.02em to -0.035em). Body and labels use normal tracking; numeric mono uses ≤0.06em. Tracked-out uppercase (`tracking-[0.12em]` and friends, in any font) is prohibited as a decorative label pattern. It is the SaaS / dev-tool reflex the AI Slop Test rejects.

**The Quiet-Label Rule.** Eyebrows, taglines, summary lines, and captions render in Inter, sentence case, small (12–13px), normal tracking, muted color. No uppercase. No tracked-out caps. No mono-as-decoration. IBM Plex Mono is reserved for genuinely numeric content (dates, times, coordinates, identifiers), never for label decoration. (This rule replaces the earlier Eyebrow-Mono Rule; that pattern read as AI/SaaS reflex.)

## 4. Elevation

The current implementation is **flat-by-default with hairlines**: surfaces use `border-ink/10` to `border-ink/15` to convey edges, and hover applies a 1px transform-Y lift with a border darken, not a shadow bloom. Two shadow tokens (`card`, `cardHover`) exist in `tailwind.config.ts` but are sparingly applied.

**Direction (PRODUCT decision):** the design should move toward slightly more lifted surfaces than the code currently honors. Reach for: subtle ambient shadow on cards at rest (`card`), a stronger ambient on hover (`cardHover`), and tonal layering for grouped regions. Hairlines remain the default edge treatment; shadows are an addition, not a replacement.

### Shadow Vocabulary

- **card** (`box-shadow: 0 1px 2px rgba(15, 17, 21, 0.04), 0 4px 12px rgba(15, 17, 21, 0.04)`): Ambient lift for resting cards and elevated surfaces. Subtle enough to be felt, not seen.
- **cardHover** (`box-shadow: 0 4px 8px rgba(15, 17, 21, 0.06), 0 12px 28px rgba(15, 17, 21, 0.08)`): Hover state on lifted cards. Pair with the 1px transform-Y lift; never apply standalone.

### Named Rules

**The Hairline-Plus-Lift Rule.** Edges live in 1px borders tinted from ink (`border-ink/10` to `border-ink/15`). Depth is a 1px translate on hover, optionally with a tonal shadow. No glow, no double-shadow, no inner shadow.

**The Quiet-Shadow Rule.** Shadows are tonal (ink-tinted) and low-opacity (≤0.08). No black shadows. No colored shadows. Two flavors are allowed:

- **Card shadow:** small blur (≤12px primary blur, ≤28px diffusion), used for the resting / hover lift on cards.
- **Sticky-overlay halo:** large blur (up to ~40px) at ≤0.08 opacity, used to separate a sticky / overlaying surface from content scrolling beneath it. Only paired with a glass surface (see The Three-Glass Rule).

Outside those two flavors, if a shadow is visible enough to describe its blur radius from across the room, it is too strong.

## 5. Components

### Buttons

- **Shape:** Gently rounded (8px, `rounded-lg`).
- **Primary:** Solid ink background (#0f1115), canvas text (#ffffff), 12px × 24px padding (`py-3 px-6`), minimum 12-unit height for touch (`min-h-12`). Used for the single high-confidence CTA per region ("Browse events", "Submit an event").
- **Hover / Focus:** Opacity-85 transition on hover (200ms). Focus-visible draws a 3px ink outline with 3px offset and a 5px canvas ring (defined globally via `.interactive-focus`). No background-shift on hover; no transform.
- **Inline icon trailing:** Optional 16px stroke-current SVG, animated 2px on group-hover (`group-hover:translate-x-0.5`). Use sparingly; primary CTA buttons earn it, secondary actions do not.
- **Secondary / Tertiary:** Not yet codified. When introduced, prefer outline-ink over filled-secondary, and prefer underlined-link over outline-button when the action is navigational.

### Cards

- **Corner Style:** Generous rounding (16px, `rounded-xl`).
- **Background:** Canvas (#ffffff) on Surface (#fafafa) page; never bare-on-canvas. Cards sit on a tonal step.
- **Border:** Hairline ink-tinted (`border-ink/15`). Hover darkens to full ink edge.
- **Shadow Strategy:** Reach for `card` at rest, `cardHover` on hover. See Elevation.
- **Internal Padding:** 16px (`p-4`) for compact, 16–20px (`px-4 py-3` to `px-5 py-4`) for text rows. Image cards use a `4/5` aspect ratio with bottom-anchored overlay copy.
- **Card-Hover Treatment:** 1px transform-Y lift, 180ms ease, border darkens to ink. Defined globally via `.card-hover`. Hover is canceled under `prefers-reduced-motion`.

### Event Card (signature)

The project's distinctive component. Two variants from the same data.

- **Image variant:** When the event has a flyer image, the card renders the flyer at `4/5` aspect, with a top-to-bottom gradient overlay (`from-ink/90 via-ink/50 to-transparent`) anchoring overlay copy at the bottom. Title in Bricolage 16–18px, date in IBM Plex Mono uppercase, category as a `bg-white/15` glass pill with `backdrop-blur-sm`. This is the only place glass-blur is sanctioned.
- **Text variant:** When there is no flyer, the card renders as a horizontal row with a 4px solid **category rail** down the left edge (`w-1`) and a hairline-bordered text block to its right. Time + location in IBM Plex Mono meta; title in Bricolage Display Title; host and category badge below. Right-edge chevron icon shifts color on group-hover.

### Category Rail (signature, with a caveat)

The 4px colored stripe on the left edge of text-variant Event Cards. This is the **only sanctioned use** of a colored side-stripe pattern in the system. It exists because event category is a primary scannable signal, and the rail lets a student parse twenty cards in two seconds by hue alone.

Do not propagate this pattern to other components. New cards, alerts, callouts, list items: full hairline border, full-bleed tinted background, or leading icon. Never another left-stripe.

### Badges (Category Pills)

- **Style:** Pill (rounded-full), 10px × 4px padding (`px-2.5 py-0.5`), 11px medium weight, 0.01em tracking.
- **Color logic:** Background uses the category color at 10–15% opacity; text uses the matched darker variant for AA contrast. The four matched pairs are documented under Colors.
- **Overlay variant:** When rendered over an image (flyer overlay), the pill uses `bg-white/15` glass with `backdrop-blur-sm` and white text. This is the second sanctioned glass usage.

### Inputs / Fields

- **Style:** Canvas background, hairline ink border, 8px radius (`rounded-md`), 10–12px vertical padding, Inter body text at 16px. (Spec; the submit form should be audited against this and brought into line if it drifts.)
- **Focus:** Uses the global `.interactive-focus` treatment: 3px ink outline, 3px offset, 5px canvas ring. Consistent with buttons. No glow, no border color shift.
- **Error / Disabled:** Not yet codified. When introduced, errors use Deep Coral text and a coral-tinted background; disabled drops to muted text on surface background.

### Sticky Filter Bar (signature)

The horizontal filter bar that pins to the top of `/events` while the events grid scrolls beneath it. The site's third sanctioned glass surface (see The Three-Glass Rule).

- **Surface:** `bg-white/55 backdrop-blur-xl` glass. The bar is intentionally translucent so the content scrolling beneath is felt, not hidden.
- **Edge:** `border-b border-white/50` on the bottom; a soft white-tinted edge rather than the standard ink hairline, because the bar overlays content.
- **Halo:** `shadow-[0_16px_40px_rgba(15,17,21,0.08)]` ambient halo. Large blur, low opacity, ink-tinted. The shadow is what separates the bar from the cards behind it; without it the bar would feel detached. Sanctioned under the second flavor of The Quiet-Shadow Rule.
- **Internals:** View toggle (tabs) + search input on row 1, category chips on row 2. Search input uses the minimal bottom-border-only treatment, not the standard full-bordered input style; this is intentional for in-bar inline search.
- **Do not copy** this treatment to non-sticky bars. The glass + halo is what justifies the design language; on a static bar it reads as decoration.

### Navigation (Masthead)

- **Style:** Sticky 56px-tall bar (`h-14`), glass variant by default (`bg-white/40 backdrop-blur-xl`), solid variant available with `border-b border-ink/10 bg-canvas/95 backdrop-blur` for routes that need a stronger separation.
- **Typography:** Brand wordmark in Bricolage Display 18–22px semibold, tight tracking. Nav links in Inter 14px medium with `hover:text-ink/70` color shift, 200ms transition. The split brand mark (`highlander/hub`) is a fixed treatment; do not stylize the slash.
- **Active states:** Underline-from-active for tabbed sections (defined globally via `.tab[aria-selected="true"]::after`).
- **Mobile treatment:** Nav links shrink to 13px medium. No hamburger; the two links inline.

### Tabs

Underlined-bottom-of-active pattern (defined in `globals.css` via `.tab`). Active: ink color + 2px ink underline 1px below the tab. Inactive: muted color, no underline. 10px / 2px padding. Use for filter switching on the events page, never for primary navigation.

### Hairline

A 1px ink-tinted divider (`.hairline` in `globals.css`). The system's preferred separator. Use this instead of `<hr>`, instead of empty card containers, instead of background-shift divisions.

### Flyer Marquee (signature)

A continuously scrolling, full-bleed strip of upcoming event flyers representing the physical campus bulletin wall, alive.
- **Scroll Track:** Continuous flex row of `FlyerTile` components (`gap-3 py-3`).
- **Velocity:** Gentle, automated horizontal crawl (32px per second, `SPEED_PX_PER_SEC`), implemented via a requestAnimationFrame loop with sub-pixel carry to avoid jumping.
- **Micro-interactions:** Auto-scrolling pauses instantly on pointer enter/focus capture and resumes on pointer leave/blur capture.
- **Accessibility:** Repeated decorative clone cards are kept out of the focus order (`tabIndex={-1}`) and hidden from screen readers (`aria-hidden="true"`) to prevent double-announcement.
- **Reduced Motion:** If `prefers-reduced-motion: reduce` is active, the automated scrolling loop is entirely disabled and it remains a standard manual touch/swipe scroller.

### Marquee (utility)

A clean horizontal message ticker used as an active separator or alert bar below the masthead.
- **Container:** Standard canvas background with a hairline bottom border (`border-b border-ink/10 py-2`).
- **Notification Dot:** A pulsing green leaf-colored dot (`bg-leaf`) using `animate-ping` to signal fresh content.
- **List items:** A horizontal flex track of key announcements separated by subtle neutral middle dots (`·`).

## 6. Do's and Don'ts

### Do:

- **Do** keep the hue-as-meaning discipline: color signals category, full stop. If you reach for a color and it is not a category, stop and use type weight or spacing.
- **Do** use Bricolage Grotesque for any display or headline role, Inter for body, IBM Plex Mono for labels, dates, and times. Three fonts. No fourth.
- **Do** keep eyebrows, taglines, and summary lines quiet: Inter, small (12–13px), sentence case, normal tracking, muted color. The "edited bulletin caption" look, not the "SaaS landing eyebrow" look.
- **Do** reserve IBM Plex Mono for content that is genuinely numeric (dates, times, coordinates, identifiers), never as decorative label-style.
- **Do** prefer hairline-bordered surfaces (`border-ink/10` to `border-ink/15`) over background-tinted ones for default cards and rows.
- **Do** ease motion out only (`cubic-bezier(0.16, 1, 0.3, 1)`). Durations: 180–300ms for state, 700–800ms for entrance. Always.
- **Do** honor `prefers-reduced-motion` on anything you add. The root `globals.css` already cancels animation duration globally; do not opt back in.
- **Do** treat the FlyerTile image-card and the text-with-category-rail variant as **the two canonical ways** to render an event. New event surfaces should use one of these two.
- **Do** use the `.interactive-focus` global class on every interactive element. Focus is non-negotiable; this is the WCAG AA commitment from PRODUCT.md made concrete.
- **Do** size for a phone first. Layouts target mobile breakpoints first, then expand. Touch targets ≥44×44px.

### Don't:

- **Don't** ship the **generic SaaS landing** look. No hero-metric templates, no identical icon-heading-text card grids, no gradient text, no stock photos of diverse-people-smiling-at-laptops. If a section could land on a Y Combinator company's homepage unchanged, rework it.
- **Don't** ship **university .edu CMS energy**. No institutional navy headers, no brochure-density link soup, no accessibility-as-checkbox afterthought. UCR.edu is not Hub.
- **Don't** ship the **Eventbrite / Meetup transactional** look. No ad-cluttered list rows, no RSVP-button stripes, no dated marketplace chrome.
- **Don't** use `border-left` or `border-right` greater than 1px as a colored accent on any component except the sanctioned **Category Rail** on text-variant Event Cards. No new colored side-stripes anywhere else.
- **Don't** use `background-clip: text` with a gradient. Gradient text is decorative-only and never carries meaning here. Emphasis is weight, size, and color, not gradient.
- **Don't** introduce new pure-#000 or pure-#fff values in any new code. Use `ink` (#0f1115) and `canvas` (#ffffff is a legacy carry; do not extend it into new contexts) and tint every new neutral toward the cool ink hue.
- **Don't** apply glassmorphism (backdrop-blur, frosted surfaces) outside the three sanctioned uses: the Masthead glass variant, the image-overlay Category Pill, and the `/events` sticky filter bar. Glass is not a default surface. (**The Three-Glass Rule.**)
- **Don't** stack cards inside cards. Nested cards are always wrong; rework as sections divided by hairlines or surface-tonal shifts.
- **Don't** reach for a modal as a first thought. Exhaust inline and progressive disclosure first. Modals are usually laziness.
- **Don't** bounce or elastic motion. Ease-out only, never elastic, never spring, never overshoot.
- **Don't** animate CSS layout properties (`width`, `height`, `top`, `left`, `padding`, `margin`). Transform and opacity only.
- **Don't** write em dashes in UI copy or commit messages. Use commas, colons, semicolons, periods, or parentheses.
- **Don't** decorate labels, eyebrows, taglines, or section headers with `uppercase tracking-[...]` in any font. That pattern is the SaaS / dev-tool reflex the AI Slop Test rejects. Use sentence-case Inter at small size, muted color.
- **Don't** add a fourth font, a fourth radius scale, or a sixth typography step without retiring an existing one.
