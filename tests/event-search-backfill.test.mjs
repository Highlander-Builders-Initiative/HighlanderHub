import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

function makeSource(id, overrides = {}) {
  return {
    id,
    title: id,
    description: "",
    startsAt: "2026-05-25T18:30:00.000-07:00",
    location: "HUB",
    host: "QA",
    hostHandle: null,
    category: "social",
    tags: [],
    ...overrides,
  };
}

test("computeMissingSearchIds returns matching ids not already loaded", async () => {
  const { computeMissingSearchIds } = await importTsModule(
    "src/components/events/events-filters.ts"
  );

  const source = [
    makeSource("loaded-hack", { title: "Spring Hackathon" }),
    makeSource("deep-hack", { title: "Fall Hackathon" }),
    makeSource("deep-social", { title: "Movie Night" }),
  ];
  const loadedIds = new Set(["loaded-hack"]);

  const missing = computeMissingSearchIds(source, "hackathon", loadedIds, 200);

  // The loaded match is excluded (already rendered); the unloaded match is
  // surfaced; the non-match is ignored.
  assert.deepEqual(missing, ["deep-hack"]);
});

test("computeMissingSearchIds matches across host and tags, preserving corpus order", async () => {
  const { computeMissingSearchIds } = await importTsModule(
    "src/components/events/events-filters.ts"
  );

  const source = [
    makeSource("by-host", { host: "Hackathon Club", startsAt: "2026-05-25T10:00:00.000-07:00" }),
    makeSource("by-tag", { tags: ["hackathon"], startsAt: "2026-05-26T10:00:00.000-07:00" }),
  ];

  const missing = computeMissingSearchIds(source, "hackathon", new Set(), 200);

  assert.deepEqual(missing, ["by-host", "by-tag"]);
});

test("computeMissingSearchIds returns nothing for an empty query and respects the cap", async () => {
  const { computeMissingSearchIds } = await importTsModule(
    "src/components/events/events-filters.ts"
  );

  const source = Array.from({ length: 5 }, (_, i) =>
    makeSource(`e${i}`, { title: "Hackathon" })
  );

  assert.deepEqual(computeMissingSearchIds(source, "", new Set(), 200), []);
  assert.equal(
    computeMissingSearchIds(source, "hackathon", new Set(), 3).length,
    3
  );
});

test("search backfill is wired through the data, API, and feed layers", () => {
  const data = read("src/lib/events/index.ts");
  const route = read("src/app/api/events/route.ts");
  const api = read("src/lib/events/api.ts");
  const hook = read("src/components/events/useEventSearchBackfill.ts");
  const browser = read("src/components/events/EventsBrowser.tsx");

  // Server resolves full records for an id set, bounded.
  assert.match(data, /export async function getEventsByIds\(ids: string\[\]\)/);
  assert.match(data, /export const EVENTS_BY_IDS_LIMIT = 200;/);
  assert.match(route, /searchParams\.get\("ids"\)/);
  assert.match(route, /getEventsByIds\(ids\)/);
  assert.match(api, /export async function fetchEventsByIds\(/);

  // Client backfill caps fetches and the feed augments + suppresses paging.
  assert.match(hook, /const MAX_BACKFILL = 200;/);
  assert.match(browser, /useEventSearchBackfill\(/);
  assert.match(browser, /mergeUniqueEventsByStart\(loadedEvents, backfillEvents\)/);
  assert.match(browser, /const feedHasMore = hasMore && !isSearching;/);
});
