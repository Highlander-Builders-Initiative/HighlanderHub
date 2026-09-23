---
name: Highlander Hub
description: A scannable campus and club events bulletin for UC Riverside.
colors:
  canvas: "#ffffff"
  surface: "#fafafa"
  line: "#e7e7e9"
  ink: "#0f1115"
  muted: "#6b7280"
  faint: "#8a909a"
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
    fontFamily: "Bricolage Grotesque, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  meta:
    fontFamily: "Bricolage Grotesque, ui-sans-serif, system-ui, sans-serif"
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

The system reads as **edited and paper-confident**: display type does the work, chrome stays hairline-thin, and the page is built to be skimmed in five seconds before it asks for any commitment. Color is tightly rationed and meaningful (the category palette is the only place hue lives); everything else sits in tinted neutrals. The voice is warm, never corporate; specific to UCR, never genericized. The brand personality from PRODUCT.md, **warm, curated, quick**, is enforced visually by a small set of doctrine: tinted neutrals, two faces (Bricolage Grotesque for display and body, IBM Plex Mono for numerics), and a Restrained color strategy that holds accent usage well below 10% of any surface.

The system explicitly rejects three aesthetic families called out as anti-references in PRODUCT.md: **generic SaaS landing** (hero-metric templates, identical card grids, gradient text), **university .edu CMS** (institutional navy soup, brochure density, slow chrome), and **Eventbrite / Meetup transactional** (ad clutter, RSVP-button soup, marketplace dating). If a screen could be confused for any of those at a glance, it has failed.

**Key Characteristics:**
- Hairline-bordered surfaces; hover darkens the edge and nothing moves; no shadow blooms (see Elevation for direction).
- Bricolage Grotesque carries display and body; IBM Plex Mono carries numerics. Two faces, never a third.
- OKLCH thinking, hex frontmatter; tinted neutrals only, no pure #000.
- Restrained color strategy: category accents at ≤10% of any surface, expressed as bright tinted washes (18%) plus a darker matched text color for AA contrast.
- Mobile-first: every layout is designed for a phone first, scaled out.
- Motion is decelerating-only (ease-out-expo), no bounce, no elastic, reduced-motion honored at the root.

## 2. Colors: The Tag Palette

The palette is a wide, tinted-neutral page with seven bright accent hues used **only** as event-category signals. Neutrals carry layout; hues carry meaning.

### Category tag palette

Seven bright hues (the `tag` colors in `tailwind.config.ts`, mapped per category in `@/lib/category-colors`) exist as **category signals**, not decoration. Tags are bright on purpose: the earlier muted editorial hues (Iris, Forest, Sage…) read as colorless. Each hue is used as an 18% wash with a matched ring, and pairs with a darker `-ink` for its text (≥4.9:1 on that wash).

- **Blue** (#1f6bff, ink #1450d8): "Club."
- **Violet** (#8b4dff, ink #6230e0): "Academic."
- **Coral** (#ff5433, ink #b82c14): "Social", and the Deadline tag.
- **Cyan** (#00b3dc, ink #006a88): "Sports."
- **Magenta** (#e83cc8, ink #a8168f): "Arts."
- **Green** (#1fc254, ink #0e7432): "Community."
- **Amber** (#ffb300, ink #9a5800): "Free Food."

"Career" reuses **Ink** as its category color (no third neutral is invented).

The home hero's highlight words ("Free food, club nights, …") use each category's `-ink` text color, and each links to the feed filtered to its category (`/events?cat=…`), marked by a hairline `ink/20` underline that takes the word's color on hover. The older editorial hues (`highlander`, `leaf`, `coral`, `sky`, `gold`, `plum`, `sage` and their `deep-` pairs) remain only for admin error states, the flyer placeholder tint and the calendar heat; they are no longer category colors.

### Neutral

- **Canvas** (#ffffff): The default page background.
- **Surface** (#fafafa): One tonal step up for sectioned regions, marquee strips, subtle backgrounds.
- **Line** (#e7e7e9): Border / divider / hairline. Used as `border-ink/10` or `border-ink/15` in the codebase.
- **Ink** (#0f1115): Primary text. A near-black with a slight cool tint, never pure #000.
- **Muted** (#6b7280): Secondary text, eyebrow labels, meta information.
- **Faint** (#8a909a): The Event Card's time, hosts and location, and the weekday in the feed's day headings ("Today **Tuesday**", "Sep 24 **Thursday**"). A softer, Luma-like read at 3.2:1 on canvas, a deliberate exception to WCAG AA for that meta; everything else secondary stays Muted.

### Dark mode

The site follows the device's light/dark setting (`prefers-color-scheme`); there is no in-page toggle. Every color above is a CSS variable in `globals.css` (RGB channels, read by `tailwind.config.ts`), and the dark block re-points the same names, so components keep writing `bg-canvas`, `text-ink`, `border-ink/10` and get both themes.

- **Canvas** (#1e1f22) and **Surface** (#151618): soft charcoals at Luma's levels (card #1e1e1e, page #151515), with only a trace of the cool tint; never near-black. Canvas stays a step above surface, the same order as light mode, so white-card-on-surface layouts become lifted-card-on-darker-page.
- **Ink** (#eceef1), **Muted** (#bec0c4), **Faint** (#a6a8ac): muted and faint keep light mode's steps below ink as measured by APCA (about 70% and 56% of ink's contrast), not by WCAG ratio. The WCAG ratio flatters light-on-dark text: matching light mode's 4.8:1 and 3.2:1 left them reading roughly half as strong.
- **Tag `-ink`s** lighten (for example blue #86a9ff) to stay ≥5.9:1 on their 18% washes. The vivid tag hues themselves do not change.
- **Scrim** (always dark): modal backdrops and the gradient behind white flyer captions. `ink` turns light in dark mode, so it must never be used for either. Text on an ink fill is `text-canvas`, not `text-white`.
- **Hairlines soften.** In dark mode a card already sits a visible step above the page, so a full-strength hairline double-edges it. Ink edges (`border-`, `ring-`, `divide-ink/N` and `.hairline`) take their opacity to the power 1.3 (`--edge-alpha-curve`): `/10` renders at ~5%, about 9 levels above the card, as on Luma. Solid `border-ink` is unaffected (1ⁿ = 1), so focus and hover edges keep their weight. Draw separators as borders, not `bg-ink/N` fills, so they follow the curve.
- **Campus Skyline** turns to dusk: the art multiplies into a night gradient that meets the canvas at its top edge.

### Named Rules

**The One Voice Rule.** Category color appears as a tinted wash (`CATEGORY_PILL`, 18% opacity), never as a saturated fill behind content. Total accent coverage on any screen stays at or below 10% of the surface. Saturated category color appears only at the 6px Category Dot size: `EventsMiniCalendar` (day-cell dots) and `ActiveFilterChips` (category chip dot). One palette, one visual language.

**The Tinted-Neutral Rule.** No new pure-hex grayscale values. Every neutral tints toward the cool ink hue. If you need a step between `surface` and `line`, derive it from the existing ramp, do not invent a flat gray.

**The Meaning-Carrying Rule.** Hue is for category. If a UI element uses color but is not signaling a category, it is wrong. Promotional accents, decorative gradients, mood-color washes: prohibited.

## 3. Typography

**Display & Body Font:** Bricolage Grotesque (with `ui-sans-serif, system-ui, sans-serif` fallback)
**Numeric / Mono Font:** IBM Plex Mono (with `ui-monospace, monospace` fallback)

**Character:** Bricolage Grotesque carries both display and body. At display sizes (28–72px) it runs with optical-sizing on, semibold weight, and negative tracking (-0.02 to -0.035em). At body sizes (16px / 1.55 line-height) the same family drops to regular weight, neutral tracking, and the variable font's `opsz` axis automatically picks the body master, reading quiet and magazine-like. Meta strings (13px, muted) use the same family without uppercase or tracked-out treatment. IBM Plex Mono is reserved for content that is genuinely numeric (dates, times, location coordinates, identifiers), never decorative caps. A single-family display+body pairing reads more confidently edited than the earlier Bricolage-over-Inter pairing did, and it is one fewer face for the AI Slop Test to flag (Inter, alongside Roboto, Geist, and Plus Jakarta Sans, has become a reflex font on the web).

### Hierarchy

- **Display** (600 weight, `clamp(2.25rem, 5.5vw, 4.5rem)`, line-height 1.0, tracking -0.035em): Hero headlines only. One per page.
- **Headline** (600, 1.75rem / 28px, line-height 1.15, tracking -0.02em): Section openers (Features, FinalCTA, page titles).
- **Title** (600, 1.125rem / 18px, line-height 1.2, tracking -0.015em): Event card titles, card-level headings. Two-line clamp.
- **Body** (400, 1rem / 16px, line-height 1.55): Paragraph text. Cap line length at 65–75ch.
- **Meta** (400, 0.8125rem / 13px, line-height 1.4, normal tracking): Quiet labels above or beside primary content: eyebrows, taglines, summary lines, captions. Bricolage Grotesque regular, sentence case, muted color. No uppercase, no tracking-out.
- **Numeric** (400, 0.6875–0.75rem / 11–12px, line-height 1, light tracking ≤0.06em, sentence case): Dates, times, location strings, identifiers, calendar grid numbers. IBM Plex Mono. Used only where the content is genuinely numeric or coordinate-like, never as decorative label-style. The home dateline anchors at 12px (top of range); secondary tabular usages (filter counts, event time strips) sit at 11px.

### Named Rules

**The Two-Face Rule.** Bricolage Grotesque carries display and body. IBM Plex Mono carries numerics. Those are the two faces. No third font is added without retiring one of the two. (This rule replaces the earlier One-Display Rule, which assumed a separate body face; Inter was retired when its overuse on the web outweighed the contrast it provided against the display.)

**The Tracking Rule.** Display type tracks tight (-0.02em to -0.035em). Body and labels use normal tracking; numeric mono uses ≤0.06em. Tracked-out uppercase (`tracking-[0.12em]` and friends, in any font) is prohibited as a decorative label pattern. It is the SaaS / dev-tool reflex the AI Slop Test rejects.

**The Quiet-Label Rule.** Eyebrows, taglines, summary lines, and captions render in Bricolage Grotesque regular, sentence case, small (12–13px), normal tracking, muted color. No uppercase. No tracked-out caps. No mono-as-decoration. IBM Plex Mono is reserved for genuinely numeric content (dates, times, coordinates, identifiers), never for label decoration. (This rule replaces the earlier Eyebrow-Mono Rule; that pattern read as AI/SaaS reflex.)

## 4. Elevation

The current implementation is **flat-by-default with hairlines**: surfaces use `border-ink/10` to `border-ink/15` to convey edges, and hover darkens the border, not a shadow bloom. Cards do not move on hover. Two shadow tokens (`card`, `cardHover`) exist in `tailwind.config.ts` but are sparingly applied.

**Direction (PRODUCT decision):** the design should move toward slightly more lifted surfaces than the code currently honors. Reach for: subtle ambient shadow on cards at rest (`card`), a stronger ambient on hover (`cardHover`), and tonal layering for grouped regions. Hairlines remain the default edge treatment; shadows are an addition, not a replacement.

### Shadow Vocabulary

- **card** (`box-shadow: 0 1px 2px rgba(15, 17, 21, 0.04), 0 4px 12px rgba(15, 17, 21, 0.04)`): Ambient lift for resting cards and elevated surfaces. Subtle enough to be felt, not seen.
- **cardHover** (`box-shadow: 0 4px 8px rgba(15, 17, 21, 0.06), 0 12px 28px rgba(15, 17, 21, 0.08)`): Hover state on lifted cards. Pair with the darkened hover edge; never apply standalone.

### Named Rules

**The Hairline-Plus-Lift Rule.** Edges live in 1px borders tinted from ink (`border-ink/10` to `border-ink/15`). Hover darkens the edge, optionally with a tonal shadow; the card itself stays put. No glow, no double-shadow, no inner shadow.

**The Quiet-Shadow Rule.** Shadows are tonal (ink-tinted) and low-opacity (≤0.08). No black shadows. No colored shadows. Two flavors are allowed:

- **Card shadow:** small blur (≤12px primary blur, ≤28px diffusion), used for the resting / hover lift on cards.
- **Sticky-overlay halo:** large blur (up to ~40px) at ≤0.08 opacity, used to separate a sticky / overlaying surface from content scrolling beneath it. Only paired with a glass surface (see The Three-Glass Rule).

Outside those two flavors, if a shadow is visible enough to describe its blur radius from across the room, it is too strong.

## 5. Components

### Buttons

- **Shape:** Gently rounded (8px, `rounded-lg`).
- **Primary:** Solid ink background (#0f1115), canvas text (#ffffff), 12px × 24px padding (`py-3 px-6`), minimum 12-unit height for touch (`min-h-12`). Used for the single high-confidence CTA per region ("Browse events").
- **Hover / Focus:** Opacity-85 transition on hover (200ms). Focus-visible draws a 3px ink outline with 3px offset and a 5px canvas ring (defined globally via `.interactive-focus`). No background-shift on hover; no transform.
- **Inline icon trailing:** Optional 16px stroke-current SVG, animated 2px on group-hover (`group-hover:translate-x-0.5`). Use sparingly; primary CTA buttons earn it, secondary actions do not.
- **Secondary / Tertiary:** Not yet codified. When introduced, prefer outline-ink over filled-secondary, and prefer underlined-link over outline-button when the action is navigational.

### Cards

- **Corner Style:** Generous rounding (16px, `rounded-xl`).
- **Background:** Canvas (#ffffff) on Surface (#fafafa) page; never bare-on-canvas. Cards sit on a tonal step.
- **Border:** Hairline ink-tinted (`border-ink/15`). Hover darkens to full ink edge.
- **Shadow Strategy:** Reach for `card` at rest, `cardHover` on hover. See Elevation.
- **Internal Padding:** 16px (`p-4`) for compact, 16–20px (`px-4 py-3` to `px-5 py-4`) for text rows. Image tiles use a `4/5` frame (Instagram's portrait post) with bottom-anchored overlay copy; flyers of other shapes follow The Whole-Flyer Rule.
- **Card-Hover Treatment:** the border darkens, 180ms ease; nothing moves. Defined globally via `.card-hover`. (The earlier 1px lift was retired: the edge change is feedback enough, and phones never hover.)

### Event Card (signature)

Feed listing row, laid out like a Luma event row: text on the left, the flyer pinned at the top-right.

Type runs larger than the system's `meta` token, matched to Luma's rows; phone sizes first, `sm+` in parentheses.

- **Time** (14px (15px), `tabular-nums text-faint`): start time as "7:00 PM". Deadlines read "Due 11:59 PM", with "Due" in `font-medium text-deep-coral`.
- **Title** (`font-display` 18px (20px) `font-semibold`, `line-clamp-2`, `mt-2` below the time). No hover underline; the card's darkened edge carries the hover.
- **Hosts row** (14px (16px) `text-faint`): up to three 16px `ClubAvatar`s overlapping by 4px, each cut out from the next by a 2px canvas ring, then, 8px on, "By A, B & C" truncated to one line. A club without a picture shows its monogram. 16px is Luma's proportion, an avatar about the text's size; the old 22px avatar ran twice the cap height and pushed the byline 12px past the location.
- **Location row** (same size and color): a 1em pin (or a 1em-wide video icon for online events), in the text's color, centered in the same 16px column as the first avatar with the same 8px gap, so the location starts at the byline's x. The icon's viewBox hugs its ink, so the pin nearly fills the column (16px tall at `sm+`) and sits ~9.5px (phones ~10.3px) from its text, close to the avatar's 8px, as on Luma. (A 24-unit icon box left ~5px of air in the column, and the pin read 13px from its text.) With several hosts the byline starts after the stack; the location stays with the first avatar.
- **Tags row** (`mt-4`, about 21px from the pin to the pill edge as on Luma; wraps): pills at 13px (14px) medium, `rounded-full`, from `eventTags` (the detail header renders the same list at 12px), in this order:
  - `Deadline` (`DEADLINE_PILL`, the coral wash), deadlines only.
  - The category ("Academic", "Social", …), in the same `CATEGORY_PILL` wash the Topics rail uses for that category when selected, so the two read as one signal. Skipped for the Free food category, which the next pill covers.
  - `Free food` (the `free_food` wash), when `hasFreeFood` or the category is Free food.
  - `RSVP` (unfilled: `ring-ink/15 text-ink/70`), when `rsvpRequired`. It notes something to do before going, not a kind of event, so it carries no fill.
- **Flyer slot** (120×150, shrinking on narrow phones to `clamp(80px, 100vw - 263px, 120px)` wide at 4:5; optional): the slot takes the width left once the text column has 181px, its width on a 375px phone, so it reaches 120×150 from a 383px screen and bottoms out at the old 80×100 below 344px. The fixed 80×100 phone slot was too small to read a flyer at, and left ~50px of empty card under it. the flyer is pinned whole at its own shape (`FlyerPoster`), anchored to the slot's top-right corner, 8px radius, `ring-ink/10` hairline. A 4:5 placeholder holds the slot while the image loads. See The Whole-Flyer Rule.

Padding is `p-4` / `sm:p-5` with a `gap-4` / `sm:gap-5` gutter between text and flyer. The card has no description; the detail view carries it.

The time column with its 2px category rail, and before it the leading category dot, have both been retired: a reader had to decode a color to get the category, and both cost width. The category now reads as a labeled pill.

**The Whole-Flyer Rule.** A flyer is never cropped to fit a box. Club posts arrive in every Instagram shape (4:5 and 3:4 portrait, 1:1, 9:16 reel covers, landscape), so each surface gives the flyer a fixed slot for rhythm and shows the flyer whole, at its own shape, inside it. The frame (radius, hairline, shadow) is drawn on the flyer itself, never on an empty crop box. `FlyerPoster` and `.flyer-poster` implement it: the slot sets `--flyer-max-w` / `--flyer-max-h`, and until the image reports its shape the poster holds a 4:5 placeholder, so space is reserved and nothing shifts. Where the flyer sits above text (the phone detail hero), a shape that arrives after first paint centers in the reserved space instead of resizing it. One exception: a wall tile fills edge to edge when the flyer is within ~8% of the tile's shape, because a trim that small cannot be seen; every other shape is pinned whole on the tile. (The earlier story-era thumbnail, a tall crop stretched to the row's height, cut the sides off every post.)

### Category Dot (signature)

A 6px colored dot (`h-1.5 w-1.5 rounded-full`) is the system's category signal. Used in exactly two places, always at the same size and palette:

1. **EventsMiniCalendar day cells**: up to three dots at `bottom-1`, encoding which categories have events that day. A density-by-type signal.
2. **ActiveFilterChips**: leads the category chip in the filter row above the feed.

Both use `CATEGORY_RAIL` from `@/lib/category-colors`:

```ts
{ club: "bg-tag-blue", academic: "bg-tag-violet", social: "bg-tag-coral",
  career: "bg-ink", sports: "bg-tag-cyan", arts: "bg-tag-magenta",
  community: "bg-tag-green", free_food: "bg-tag-amber" }
```

The two surfaces speak the same color language: pick "Free Food" in the chip-bar and gold dots leap out of the calendar at the same time. That coupling is the whole point of the dot; do not invent a separate palette for a third surface.

Event cards once carried a colored side-stripe rail, and later a dot leading the title; both are retired (see Event Card). Having a single side-stripe carve-out invited propagation, so the carve-out itself is gone (see the side-stripe rule under Don't).

### Badges (Category Pills)

- **Style:** Pill (rounded-full), 10px × 4px padding (`px-2.5 py-0.5`), 12px medium weight, 0.01em tracking.
- **Color logic:** The same `CATEGORY_PILL` wash as the Event Card's tags: the category hue at 18% with its matched `-ink` text for AA contrast. The pairs are documented under Colors.
- **Overlay variant:** When rendered over an image (flyer overlay), the pill uses `bg-white/15` glass with `backdrop-blur-sm` and white text. This is the second sanctioned glass usage.

### Inputs / Fields

- **Style:** Canvas background, hairline ink border, 8px radius (`rounded-md`), 10–12px vertical padding, Bricolage Grotesque body text at 16px.
- **Focus:** Uses the global `.interactive-focus` treatment: 3px ink outline, 3px offset, 5px canvas ring. Consistent with buttons. No glow, no border color shift.
- **Error / Disabled:** Not yet codified. When introduced, errors use Deep Coral text and a coral-tinted background; disabled drops to muted text on surface background.

### Sticky Filter Bar (signature)

The search bar that pins to the top of the `/events` feed while the cards scroll beneath it: a 48px liquid-glass capsule (`rounded-full`, `h-12`), the site's third sanctioned glass surface (see The Three-Glass Rule).

- **Surface:** `.liquid-glass` in `globals.css`: white at 72% fading to 50% top to bottom, `blur(18px) saturate(180%)`. Clear enough that the feed is felt beneath it, saturated so a flyer's colour carries into the bar.
- **Edge:** a 1px specular rim (the `::before`), bright white along the top and fading down the sides, over a 1px ink hairline at 7%. The rim is what reads as glass over a flyer; the hairline is what keeps the capsule visible over white cards. This rim is the one sanctioned exception to "no inner shadow" in The Hairline-Plus-Lift Rule.
- **Halo:** `0 12px 32px` at 0.08, sanctioned under the second flavor of The Quiet-Shadow Rule.
- **Placement:** from `lg`, the capsule floats free at `top-3`, the width of the feed column, so it lines up with the cards' edges. On phones it sits in a full-bleed `bg-surface/80 backdrop-blur-xl` strip that runs on into the sticky day heading below (`top: 56`), so the feed never shows between the two. The heading carries the same frosted fill and closes the stack with an inset `ink/10` hairline aligned to the card edges.
- **Internals:** controls nest inside the capsule concentrically: 6px inset (`p-1.5`), 36px pills (`h-9 rounded-full bg-ink/[0.06]`). Left to right: the Filter pill (phones only, opens the filter sheet) or, from `lg`, the observed day ("Today **Tuesday**") at a 20px inset with a hairline divider; the search field; the back-to-top circle, which grows in once you're past the fold. The field has no border of its own. The capsule is the field.
- **Focus:** the capsule takes the input's focus ring (1.5px ink at 45%, 3.3:1 on white, with a soft 5px ink halo) and firms up to 92% white while you type. The search clear button is a gray iOS-style circle.
- **Club suggestions:** drop 8px below the capsule, full capsule width, `rounded-3xl`, with rows highlighted as concentric `rounded-[18px]` pills. Solid canvas, not glass: the capsule's backdrop-filter walls the dropdown off from the feed, so a blur there would only ghost the cards through.
- **Do not copy** this treatment to non-sticky bars. The glass + halo is what justifies the design language; on a static bar it reads as decoration.

### Active Filter Chips (signature)

The removable-chip row that renders directly below the sticky filter bar on `/events` when at least one filter is active. One chip per active filter (category, day window, query); each chip is a single pill button that drops that one filter when clicked. "Clear all" sits as a trailing text-underline link.

- **Pill style:** `min-h-11` (touch-target compliant), `rounded-full`, hairline `border-ink/15`, faint `bg-surface` lift, `text-[13px]`, `px-3.5`. Hover darkens to `border-ink`; the `×` glyph shifts from `text-muted` to `text-ink`. The whole pill is the click target; the `×` is the visual affordance only.
- **Category chip:** leads with a 6px Category Dot (see above).
- **Day-window chip:** label only.
- **Query chip:** shows the search term wrapped in curly quotes — `"diwali"`.
- **Divider:** `border-b border-ink/10` runs below the row. When no filters are active, the row and the divider both unmount; the page reads as if the chip-bar never existed.
- **A11y:** each chip is a `<button>` with `aria-label` ("Remove Free Food filter", "Clear search for diwali"). Row wrapped in `role="group" aria-label="Active filters"`. The result-count below the row carries the `aria-live="polite"` announcement when a filter is removed.

Do not copy this pattern to non-filter surfaces. The "removable chip row" reads as a filter affordance specifically; on a non-filter surface, it reads as tag-soup.

### Navigation (Masthead)

- **Style:** Sticky 56px-tall bar (`h-14`), glass variant by default (`bg-white/40 backdrop-blur-xl`), solid variant available with `border-b border-ink/10 bg-canvas/95 backdrop-blur` for routes that need a stronger separation.
- **Typography:** Brand wordmark in Bricolage Display 18–22px semibold, tight tracking. Nav links in Bricolage Grotesque 14px medium with `hover:text-ink/70` color shift, 200ms transition. The split brand mark (`highlander/hub`) is a fixed treatment; do not stylize the slash.
- **Active states:** Underline-from-active for tabbed sections (defined globally via `.tab[aria-selected="true"]::after`).
- **Links:** Events and About. No Home link; the wordmark is the way home.
- **Mobile treatment:** Nav links shrink to 13px medium, each a 44px-tall target. No hamburger; the two links inline.

### Tabs

Underlined-bottom-of-active pattern (defined in `globals.css` via `.tab`). Active: ink color + 2px ink underline 1px below the tab. Inactive: muted color, no underline. 10px / 2px padding. Use for filter switching on the events page, never for primary navigation.

### Hairline

A 1px ink-tinted divider (`.hairline` in `globals.css`). The system's preferred separator. Use this instead of `<hr>`, instead of empty card containers, instead of background-shift divisions.

### Flyer Marquee (signature)

A continuously scrolling, full-bleed strip of upcoming event flyers representing the physical campus bulletin wall, alive.
- **Scroll Track:** Continuous flex row of `FlyerTile` components (`gap-3 py-3`).
- **Tiles:** Fixed 4:5 frames, so the loop's geometry never changes as images load. Portrait posts fill the tile; squares, reel covers and landscape posts are pinned whole on it (The Whole-Flyer Rule).
- **Velocity:** Gentle, automated horizontal crawl (32px per second, `SPEED_PX_PER_SEC`), implemented via a requestAnimationFrame loop with sub-pixel carry to avoid jumping.
- **Micro-interactions:** Auto-scrolling pauses instantly on pointer enter/focus capture and resumes on pointer leave/blur capture.
- **Accessibility:** Repeated decorative clone cards are kept out of the focus order (`tabIndex={-1}`) and hidden from screen readers (`aria-hidden="true"`) to prevent double-announcement.
- **Reduced Motion:** If `prefers-reduced-motion: reduce` is active, the automated scrolling loop is entirely disabled and it remains a standard manual touch/swipe scroller.

### Campus Skyline (signature)

The hero's landmark illustration: the Bell Tower standing on the horizon line
that doubles as the hairline above the flyer wall. It replaces the abstract
navy-and-gold hero ribbon, which was decorative without being about anywhere.

- **Subject:** a single low-poly illustration
  (`components/home/campus-skyline.webp`, 4000x1484, a 2x Real-ESRGAN
  upscale of the 2000px original): the 1966 carillon against
  a low sun, the Box Springs range with the Big C cut into the hillside, and
  palms over a Riverside grove at its feet. The clock face is painted in, so
  it shows a fixed time.
- **Composition:** anchored bottom, so the tree line and the tower's base land
  on the hairline. The band's height (`--skyline-h` on `.skyline-hero`)
  tracks the art's ratio at laptop widths. On phones it keeps a 240px floor
  and crops the sides, and `object-position` holds the tower in frame. Past
  ~1940px it stops growing and crops the tree line. On phones the copy sits
  above the art; from `md` up it overlaps the open sky at left, which is why
  the copy column stays narrow.
- **Seam:** the hero fades from white into the art's sky (`#fff9f2`, sampled
  from its top edge), reaching it exactly where the image begins, so the
  picture has no visible top edge. Re-sample if the art changes.
- **Technique:** `next/image` with `preload` (it is the LCP) at `quality={90}`
  (75 bands the sky and softens facet edges), decorative
  (`alt=""`, `aria-hidden`), and no animation, so the flyer wall stays the
  only thing moving.

**The One-Landmark Rule.** This is the system's single sanctioned decorative
illustration, and it is allowed *because* it is about a specific place. It sits
behind and below the hero copy, keeps to muted, sun-washed tones so the copy
and the flyers stay the loudest things on the page, and carries no information. Do not
propagate it: no spot illustrations on other pages, no second landmark, no
tower mark in the masthead or footer. If a surface wants a picture, it almost
certainly wants a flyer instead.

This is a deliberate, bounded exception to **The Meaning-Carrying Rule**. Hue
still signals category everywhere a user can act; the skyline is scenery, is
`aria-hidden`, and never colors a control, a label, or a state.

## 6. Do's and Don'ts

### Do:

- **Do** keep the hue-as-meaning discipline: color signals category, full stop. If you reach for a color and it is not a category, stop and use type weight or spacing.
- **Do** use Bricolage Grotesque for display, headline, body, and non-numeric labels, and IBM Plex Mono for numerics (dates, times, identifiers, calendar numbers). Two faces. No third.
- **Do** keep eyebrows, taglines, and summary lines quiet: Bricolage Grotesque regular, small (12–13px), sentence case, normal tracking, muted color. The "edited bulletin caption" look, not the "SaaS landing eyebrow" look.
- **Do** reserve IBM Plex Mono for content that is genuinely numeric (dates, times, coordinates, identifiers), never as decorative label-style.
- **Do** prefer hairline-bordered surfaces (`border-ink/10` to `border-ink/15`) over background-tinted ones for default cards and rows.
- **Do** ease motion out only (`cubic-bezier(0.16, 1, 0.3, 1)`). Durations: 180–300ms for state. Always.
- **Do** honor `prefers-reduced-motion` on anything you add. The root `globals.css` already cancels animation duration globally; do not opt back in.
- **Do** treat the FlyerTile (home mosaic + marquee tiles) and the EventCard (feed listing row: time, title, host avatars, location, tags, flyer at the right) as **the two canonical ways** to render an event. New event surfaces should use one of these two.
- **Do** use the `.interactive-focus` global class on every interactive element. Focus is non-negotiable; this is the WCAG AA commitment from PRODUCT.md made concrete.
- **Do** size for a phone first. Layouts target mobile breakpoints first, then expand. Touch targets ≥44×44px.

### Don't:

- **Don't** animate content in on page load (fade-ups, staggered entrances, scale-ins). Students come back to the home page weekly; a delay that sells the site once costs them on every visit after. Motion there is the content (the Flyer Marquee), a state change (sliding highlights, the modal), or a response to input (hover).
- **Don't** ship the **generic SaaS landing** look. No hero-metric templates, no identical icon-heading-text card grids, no gradient text, no stock photos of diverse-people-smiling-at-laptops. If a section could land on a Y Combinator company's homepage unchanged, rework it.
- **Don't** ship **university .edu CMS energy**. No institutional navy headers, no brochure-density link soup, no accessibility-as-checkbox afterthought. UCR.edu is not Hub.
- **Don't** ship the **Eventbrite / Meetup transactional** look. No ad-cluttered list rows, no RSVP-button stripes, no dated marketplace chrome.
- **Don't** use `border-left` or `border-right` greater than 1px as a colored accent on any component. No colored side-stripes anywhere. (The earlier Category Rail on Event Cards has been retired; see Event Card under Components.)
- **Don't** use `background-clip: text` with a gradient. Gradient text is decorative-only and never carries meaning here. Emphasis is weight, size, and color, not gradient.
- **Don't** introduce new pure-#000 or pure-#fff values in any new code. Use `ink` (#0f1115) and `canvas` (#ffffff is a legacy carry; do not extend it into new contexts) and tint every new neutral toward the cool ink hue.
- **Don't** apply glassmorphism (backdrop-blur, frosted surfaces) outside the three sanctioned uses: the Masthead glass variant, the image-overlay Category Pill, and the `/events` sticky filter bar. Glass is not a default surface. (**The Three-Glass Rule.**)
- **Don't** stack cards inside cards. Nested cards are always wrong; rework as sections divided by hairlines or surface-tonal shifts.
- **Don't** reach for a modal as a first thought. Exhaust inline and progressive disclosure first. Modals are usually laziness.
- **Don't** bounce or elastic motion. Ease-out only, never elastic, never spring, never overshoot.
- **Don't** animate CSS layout properties (`width`, `height`, `top`, `left`, `padding`, `margin`). Transform and opacity only.
- **Don't** write em dashes in UI copy or commit messages. Use commas, colons, semicolons, periods, or parentheses.
- **Don't** decorate labels, eyebrows, taglines, or section headers with `uppercase tracking-[...]` in any font. That pattern is the SaaS / dev-tool reflex the AI Slop Test rejects. Use sentence-case Bricolage Grotesque at small size, muted color.
- **Don't** add a fourth font, a fourth radius scale, or a sixth typography step without retiring an existing one.
