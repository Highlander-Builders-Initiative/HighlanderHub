import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("event filters expose accessible state and recovery actions", () => {
  const source = read("src/components/events/EventsBrowser.tsx");

  assert.match(source, /aria-pressed=/);
  assert.match(source, /aria-live=/);
  assert.match(source, /htmlFor="event-search"/);
  assert.match(source, /id="event-search"/);
  assert.match(source, /Clear filters/);
  assert.doesNotMatch(source, /⌕/);
});

test("event browser paginates the list instead of rendering every event at once", () => {
  const browser = read("src/components/events/EventsBrowser.tsx");
  const data = read("src/lib/events.ts");
  const api = read("src/app/api/events/route.ts");

  assert.match(data, /EVENTS_PAGE_SIZE/);
  assert.match(data, /\.range\(/);
  assert.match(api, /searchParams/);
  assert.match(browser, /Load more/);
  assert.match(browser, /hasMore/);
});

test("event cards link to a detail page and stay accessible", () => {
  const source = read("src/components/events/EventCard.tsx");

  assert.match(source, /href=\{`\/events\/\$\{event\.id\}`\}/);
  assert.match(source, /aria-label=/);
});

test("event detail page exposes RSVP / calendar / share actions", () => {
  const source = read("src/app/events/[id]/page.tsx");

  assert.match(source, /Add to calendar|aria-label="Add to calendar"/);
  assert.match(source, /Share|aria-label="Share"/);
  assert.match(source, /RSVP|View source/);
});

test("masthead keeps navigation reachable on mobile", () => {
  const source = read("src/components/layout/Masthead.tsx");

  assert.match(source, /md:hidden/);
  assert.match(source, /\/events/);
  assert.match(source, /"\/about"/);
});

test("motion and focus behavior have accessible fallbacks", () => {
  const source = read("src/app/globals.css");

  assert.match(source, /prefers-reduced-motion: reduce/);
  assert.match(source, /\.interactive-focus/);
  assert.match(source, /touch-action: manipulation/);
});

test("badge colors avoid low-contrast accent text", () => {
  const source = read("src/components/ui/CategoryBadge.tsx");

  assert.doesNotMatch(source, /text-leaf/);
  assert.doesNotMatch(source, /text-coral/);
  assert.doesNotMatch(source, /text-sky/);
});

test("submit form exposes client-side validation feedback accessibly", () => {
  const source = read("src/components/forms/SubmitForm.tsx");

  assert.match(source, /validateRequiredFields/);
  assert.match(source, /aria-invalid=\{Boolean\(error\)\}/);
  assert.match(source, /aria-describedby=\{describedBy \|\| undefined\}/);
  assert.match(source, /This field is required\./);
  assert.match(source, /Required/);
});

test("site exposes crawler and social preview metadata", () => {
  const layout = read("src/app/layout.tsx");
  const eventDetail = read("src/app/events/[id]/page.tsx");
  const submitPage = read("src/app/submit/page.tsx");
  const seo = read("src/lib/seo.ts");
  const sitemap = read("src/app/sitemap.ts");
  const robots = read("src/app/robots.ts");
  const manifest = read("public/manifest.json");

  assert.match(layout, /metadataBase:/);
  assert.match(layout, /openGraph:/);
  assert.match(layout, /twitter:/);
  assert.match(layout, /manifest:/);
  assert.match(layout, /SITE_PREVIEW_IMAGE/);
  assert.match(seo, /\/logo_icon\.png/);

  assert.match(eventDetail, /openGraph:/);
  assert.match(eventDetail, /twitter:/);
  assert.match(eventDetail, /event\.imageUrl/);
  assert.match(eventDetail, /\/events\/\$\{event\.id\}/);

  assert.match(submitPage, /title: "Submit an event — Highlander Hub"/);
  assert.match(submitPage, /description:/);

  assert.match(sitemap, /MetadataRoute\.Sitemap/);
  assert.match(sitemap, /\/events/);
  assert.match(sitemap, /\/about/);
  assert.match(sitemap, /\/submit/);

  assert.match(robots, /MetadataRoute\.Robots/);
  assert.match(robots, /sitemap:/);

  assert.match(manifest, /Highlander Hub/);
  assert.match(manifest, /\/logo_icon\.png/);
  assert.match(manifest, /"start_url": "\/"/);
});
