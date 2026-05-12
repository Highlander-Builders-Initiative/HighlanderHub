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

test("event cards support visual scanning and useful actions", () => {
  const source = read("src/components/EventCard.tsx");

  assert.match(source, /event\.imageUrl/);
  assert.match(source, /Add to calendar/);
  assert.match(source, /Share/);
  assert.match(source, /aria-label=/);
});

test("masthead keeps navigation reachable on mobile", () => {
  const source = read("src/components/Masthead.tsx");

  assert.match(source, /md:hidden/);
  assert.match(source, /"#sources"/);
  assert.match(source, /"#about"/);
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
