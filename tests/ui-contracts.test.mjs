import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("event filters expose accessible state and recovery actions", () => {
  const source = read("src/components/EventsBrowser.tsx");

  assert.match(source, /aria-pressed=/);
  assert.match(source, /aria-live=/);
  assert.match(source, /htmlFor="event-search"/);
  assert.match(source, /id="event-search"/);
  assert.match(source, /Clear filters/);
  assert.doesNotMatch(source, /⌕/);
});

test("event cards link to a detail page and stay accessible", () => {
  const source = read("src/components/EventCard.tsx");

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
  const source = read("src/components/Masthead.tsx");

  assert.match(source, /md:hidden/);
  assert.match(source, /\/events/);
  assert.match(source, /"\/#about"/);
});

test("motion and focus behavior have accessible fallbacks", () => {
  const source = read("src/app/globals.css");

  assert.match(source, /prefers-reduced-motion: reduce/);
  assert.match(source, /\.interactive-focus/);
  assert.match(source, /touch-action: manipulation/);
});

test("badge colors avoid low-contrast accent text", () => {
  const source = read("src/components/CategoryBadge.tsx");

  assert.doesNotMatch(source, /text-leaf/);
  assert.doesNotMatch(source, /text-coral/);
  assert.doesNotMatch(source, /text-sky/);
});
