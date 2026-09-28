import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const read = (path) =>
  readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("about page leads with what Highlander Hub does", () => {
  const source = read("src/app/about/page.tsx");

  assert.match(source, /We read club Instagram so you don&rsquo;t have to\./);
  assert.doesNotMatch(source, /Nobody posts&nbsp;on HighlanderLink\./);
});

test("about page stays quiet: one heading style, nothing moving, no inverted band", () => {
  const source = read("src/app/about/page.tsx");
  const css = read("src/app/globals.css");

  // The landing page's type: Bricolage body copy on a brand surface.
  assert.match(source, /<main className="brand-type/);
  // Every section heading shares one style.
  assert.match(source, /const SECTION_HEADING =/);
  assert.equal(source.match(/className=\{SECTION_HEADING\}/g)?.length, 3);
  // No flyer wall, no scroll-triggered entrances, no tracked-out caps.
  assert.doesNotMatch(source, /FlyerWall|Reveal|uppercase/);
  assert.doesNotMatch(css, /flyer-wall/);
  assert.doesNotMatch(source, /bg-ink text-canvas/);
  // The answers are on the page, not behind an accordion.
  assert.doesNotMatch(source, /Accordion|AboutFaq/);
});

test("the flyer trace keeps product data in the feed's UI face, flat", () => {
  const trace = read("src/components/about/FlyerTrace.tsx");

  assert.match(trace, /<EventCard event=\{event\}/);
  assert.match(trace, /\[--font-body:var\(--font-ui\)\]/);
  assert.doesNotMatch(trace, /shadow-cardHover/);
});

test("run times follow campus time across daylight saving", async () => {
  const { campusRunTimes } = await importTsModule("src/lib/run-schedule.ts");
  // Intl puts a narrow no-break space before AM/PM.
  const times = (iso) => campusRunTimes(new Date(iso)).map((t) => t.replace(/\s/g, " "));

  assert.deepEqual(times("2026-09-27T12:00:00Z"), ["1 AM", "9 AM", "5 PM"]);
  assert.deepEqual(times("2026-12-01T12:00:00Z"), ["12 AM", "8 AM", "4 PM"]);
});
