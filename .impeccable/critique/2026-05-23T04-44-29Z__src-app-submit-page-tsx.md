@ -1,102 +0,0 @@
---
target: the submit event page
total_score: 17
p0_count: 2
p1_count: 3
timestamp: 2026-05-23T04-44-29Z
slug: src-app-submit-page-tsx
---
# Critique: /submit (src/app/submit/page.tsx + src/components/forms/SubmitForm.tsx)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | "Submitting…" is the only signal; no char counter on 200-char title, no inline progress, no required-fields preflight |
| 2 | Match System / Real World | 2 | "Source URL", "Image URL", "RSVP URL" are database vocabulary; a phone-using club officer thinks "flyer," "event page," "ticket link" |
| 3 | User Control and Freedom | 2 | No draft save, no preview before submit, no "back to edit" from the success state |
| 4 | Consistency and Standards | 1 | Entire form is orphaned from the design system: font-serif, stone-*, red-*, emerald-*, raw <hr>. Reads like it was built before DESIGN.md existed and never migrated |
| 5 | Error Prevention | 2 | Validation only on submit; datetime pickers offer no format scaffolding; tags are raw comma-typing; image URL has no preview |
| 6 | Recognition Rather Than Recall | 2 | Category picked from a dropdown with no color preview of the resulting card; no example flyer next to the URL field |
| 7 | Flexibility and Efficiency | 1 | No autocomplete for common UCR locations/hosts; comma-tag entry is brutal on mobile; no paste-from-Instagram shortcut |
| 8 | Aesthetic and Minimalist Design | 2 | 12+ inputs in one undifferentiated vertical column; a single <hr> is the only grouping; serif headline collides with the site's sans display voice |
| 9 | Error Recovery | 2 | Per-field errors are decent (good aria), but the Supabase failure path renders error.message verbatim, implementation leak to a non-technical user |
| 10 | Help and Documentation | 1 | No moderation criteria, no "what gets approved," no examples beyond two placeholder strings; users guess at what HBI wants |
| **Total** | | **17/40** | **Below the floor; this surface is silently undermining the rest of the brand** |

## Anti-Patterns Verdict

**LLM assessment:** This page would not flunk a generic AI-slop test because it isn't trying to be visually ambitious. It flunks the *product* slop test: a user fluent in Linear/Notion/Partiful would sit down, pause, and feel that the controls don't belong to the same product as the rest of Highlander Hub. The form is *earnestly bland*, not slop, but it's bland in a way that contradicts the rest of the system. That's worse than slop, it's a tone fracture.

Specific reflexes:
- The endless single-column form. 12+ fields top to bottom with no visual rhythm. Eventbrite energy, which PRODUCT.md explicitly bans.
- Paste-URLs-of-things instead of upload-things. Club officers don't host flyers on a CDN. They have JPEGs on their phone. Asking for an "Image URL" is 2010 craigslist.
- Default-Tailwind error/success palette. Stock bg-red-50 / bg-emerald-50 boxes, the most "shipped a form in a hurry" tell there is.

**Deterministic scan:** Error: bundled detector not found. The bundled detect.mjs entry doesn't resolve in this repo's impeccable skill. Deterministic scan unavailable; LLM assessment only.

**Visual overlays:** Not attempted. No reliable user-visible overlay available.

## Overall Impression

The discovery surface of Highlander Hub has had a real design system applied to it: Bricolage display, tinted neutrals, the Quad palette, the sticky filter bar, the flyer marquee. **The submit page is from before that work happened, and the rest of the site has lapped it.** That's the single biggest finding: the form isn't *bad design*, it's *the previous design*. The fix isn't make it pretty; the fix is bring it into the system everyone else already lives in.

Second largest opportunity: the form is built for a person at a desktop typing into a database. The actual user is a club officer on a phone trying to post the flyer in their camera roll between classes. Mobile-first means upload, conditional fields, fewer keystrokes, not just "responsive."

## What's Working

- **Validation logic is honest.** validateRequiredFields, validateOptionalUrlFields, validateEventTimes. The *behavior* of the form is genuinely well-built. aria-describedby, aria-invalid, per-field error IDs are all there. The accessibility scaffolding is real, not performed.
- **Tone of the success state is right.** "Got it. Your event is queued for review…" is warm, specific, finite. That's the PRODUCT.md voice. Now make it look like it belongs.
- **The page header copy** ("Got a club meeting, lecture, or anything happening at UCR? Drop the details below.") is well-pitched: campus, specific, casual without being breezy.

## Priority Issues

### [P0] The form is using a different design system than the rest of the site
**Why it matters:** Every visible class in SubmitForm.tsx is from outside the project's token set. font-serif falls back to Tailwind's default serif because **the design system has no serif**: Display is Bricolage Grotesque (sans). The form's borders are stone-400, not border-ink/15. Inputs sit on bg-stone-50, not bg-canvas over a surface page. Errors are red-700 text on red-50, success is emerald-300 on emerald-50, neither uses the Deep Coral / Deep Leaf pairs documented in DESIGN.md. The <hr className="border-stone-300" /> is exactly what DESIGN.md tells you not to write ("Use this [.hairline] instead of <hr>"). A submitter who arrives from /events will feel the discontinuity, even if they can't name it. That's a brand integrity bug, not a paint job.
**Fix:** Migrate every class. font-serif to font-display. stone-* to ink / canvas / surface / line / muted. border-stone-400 to border-ink/15, focus to border-ink. Error tints to bg-coral/10 text-deep-coral border-deep-coral/30. Success tints to bg-leaf/10 text-deep-leaf border-deep-leaf/30. Replace the <hr> with the .hairline global. Rebuild Field/SelectField/Checkbox to match the documented input spec (rounded-md, ink hairline, interactive-focus).
**Suggested command:** /impeccable craft submit-form-system-aligned (or /impeccable polish if scope stays surface-level).

### [P0] One long single-column scroll, no grouping, on a mobile-first audience
**Why it matters:** PRODUCT.md says the submit user is a club officer "submitting events through /submit, who care that their listing lands accurately and gets seen." On mobile, twelve+ inputs in a single column with one <hr> between them is the Eventbrite shape PRODUCT.md explicitly rejects. There's no implied bulletin-feel; it's a tax form.
**Fix:** Group into 3 sections with hairline dividers and a small Inter-meta eyebrow per section: "The event" (title, description, category, tags), "When and where" (start/end, location, host), "Links and image" (flyer upload, event page, RSVP), "You" (name, email, org). Drop the inline <h2>Your info</h2> and replace with the eyebrow pattern. Show a progress affordance ("3 of 4 sections") on mobile.
**Suggested command:** /impeccable shape submit-flow-grouping then /impeccable layout.

### [P1] Image entry is "paste a URL", the wrong affordance for the actual user
**Why it matters:** A UCR club officer designing a flyer in Canva and posting it from their phone has a JPEG, not a hosted URL. Asking for an Image URL means they bounce to Instagram, grab the post URL, realize that won't render, give up, or post without an image and end up in the text-rail variant of EventCard, which is worse engagement than the image variant the discovery surface is designed around. The site optimizes for flyer cards in the marquee; the submit form makes them rare.
**Fix:** Replace image_url with an upload-or-paste field. Upload to Supabase storage (the project already uses Supabase). Keep paste-URL as a secondary affordance for the rare officer who has a CDN link. Show a 4:5 preview tile (mirroring EventCard image variant) as soon as the upload resolves, so the submitter sees the exact card they're shipping.
**Suggested command:** /impeccable craft flyer-upload.

### [P1] RSVP URL is always visible regardless of the "RSVP required" toggle
**Why it matters:** Recognition-not-recall violation and an Error Prevention violation: the field invites entry even when the toggle is off, the submitter can fill it and then untoggle (or vice versa), and the resulting row is ambiguous. The pair rsvp_required: false, rsvp_url: "https://..." shouldn't be reachable.
**Fix:** Reveal the RSVP URL field inline only when "RSVP required" is on, with a 180 to 220ms ease-out-expo transition (transform/opacity only, don't animate height per DESIGN.md; use a grid-row trick or a measured max-height in a transform). On uncheck, clear the URL value and the error.
**Suggested command:** /impeccable craft conditional-rsvp-field or part of /impeccable shape.

### [P1] Datetime pickers are not the right control for "starts" / "ends"
**Why it matters:** Native datetime-local on mobile is acceptable but visually inconsistent across iOS/Android and offers no scaffolding ("Today 6 PM", "Tomorrow", "Friday evening"). For a five-second submit flow the keystroke cost is too high, and side-by-side on sm: collapses to two stacked OS pickers on phone, the form's most painful moment.
**Fix:** Either (a) a date chip row (Today / Tomorrow / This Friday / Pick…) above the time-only input, or (b) a custom date-time popover that respects DESIGN.md (Bricolage labels, IBM Plex Mono for the numeric grid, ink hairlines, no glass). End-time defaulted to start + 1 hour with one-tap +30/+60/+90 adjustments. Keep the raw input as a fallback for screen readers.
**Suggested command:** /impeccable craft datetime-input (this is real net-new work, not a polish).

## Persona Red Flags

**Maya, club officer (primary).** Has a flyer JPEG in Photos. Posting from a Mustang Express bus seat. Red flags: there's no upload, she has to host the image first; the title field has no visible character budget so she'll type something long, get clipped, find out later; the tags input wants commas, which means typing a comma on the iOS keyboard between every tag (slow + error-prone); the date+time picker takes 14 taps for a single event; the success message gives no link back to her listing or to edit, so if she made a typo she emails HBI.

**Anya, casual contributor.** A residence hall RA, not a club officer, wants to post a study session. Red flags: "Host / organization" placeholder says "ACM at UCR", implies you need to be an org, not just a person. "Source URL" jargon doesn't match her mental model (she has nothing to link to). No moderation transparency, she doesn't know if "study session" is something HBI accepts, so she may not submit at all.

**Devon, a11y user on VoiceOver, iOS.** The aria scaffolding is genuinely there: labels, error IDs, aria-invalid, aria-describedby. But: the <hr> is announced as a "horizontal separator" which is meaningless without a heading after it for "Your info"; the section heading exists but isn't programmatically tied to a group; the success state is a <div> not a role="status" live region, so it won't announce on form replacement.

## Minor Observations

- "Required" is shown on every required field individually. Most fields are required; flip the convention to "Optional" on the optional ones, quieter, and a stronger signal.
- The submit button is w-full even on desktop. After max-w-2xl constraint, that's still 672px of solid ink bar. Cap at 240 to 280px on sm: and up, or make it auto-width.
- The error banner renders error.message from Supabase verbatim. Wrap it: "Something went wrong saving this. Try again, or email us if it keeps failing." Log the raw message for the team; don't ship Postgres strings to students.
- The Tailwind placeholder:text-stone-600 is fine for contrast but it's the same text-stone-600 used for muted body, so placeholders look identical to filled-in muted text. Use text-muted/70 once the migration to system tokens lands.
- The category default of "club" is reasonable but means the dropdown is selected before the user looks at it, a subtle "did I forget to pick a category?" anxiety. Either make it explicit ("Pick one") or surface the chosen category color next to the field so the choice feels visible.
- Maxlength 200 on title is silent. Add a 0/200 counter that turns Deep Coral past 160.
- Description is rows={3}. For "what's happening, who's it for" that's too cramped. 4 to 5 rows, and auto-grow.
- track("submit_page_view", {}) fires before the form is interacted with; consider also tracking submission_first_blur to find where in the field list users abandon.

## Questions to Consider

- What does the *minimum-viable* submission look like, flyer image + title + when? Could a club officer post a real, useful listing in under 30 seconds, with everything else deferred to admin enrichment?
- What if the form were a single "paste an Instagram link" field that pre-fills 70% of the fields by scraping the post (which PRODUCT.md already says you do for ingestion)? The form would become an exception path, not the front door.
- What's the editor-side review screen, and does *that* surface accept the missing data instead of the submitter doing it? You're trusting a student volunteer to fill a 12-field row when an HBI moderator could fill the last 4 fields in batch.