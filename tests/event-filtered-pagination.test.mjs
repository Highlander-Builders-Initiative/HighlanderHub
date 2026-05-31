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
    hasFreeFood: false,
    ...overrides,
  };
}

test("shared event filters apply query, category, and day window consistently", async () => {
  const { filterEventSource } = await importTsModule(
    "src/components/events/events-filters.ts"
  );

  const source = [
    makeSource("loaded-hack", { title: "Spring Hackathon" }),
    makeSource("food-hack", {
      title: "Snack Hackathon",
      category: "club",
      hasFreeFood: true,
    }),
    makeSource("later-hack", {
      title: "Fall Hackathon",
      startsAt: "2026-06-05T18:30:00.000-07:00",
    }),
    makeSource("movie", { title: "Movie Night" }),
  ];

  assert.deepEqual(
    filterEventSource(source, {
      category: "free_food",
      dayWindow: "week",
      todayKey: "2026-05-25",
      normalizedQuery: "hackathon",
    }).map((event) => event.id),
    ["food-hack"]
  );
});

test("category counts reuse the shared filtered source", async () => {
  const { countEventsByCategory, filterEventSource } = await importTsModule(
    "src/components/events/events-filters.ts"
  );

  const filtered = filterEventSource(
    [
      makeSource("social"),
      makeSource("academic", { category: "academic" }),
      makeSource("food-flag", { category: "club", hasFreeFood: true }),
    ],
    {
      category: "all",
      dayWindow: "all",
      todayKey: "2026-05-25",
      normalizedQuery: "",
    }
  );
  const counts = countEventsByCategory(filtered);

  assert.equal(counts.get("all"), 3);
  assert.equal(counts.get("social"), 1);
  assert.equal(counts.get("academic"), 1);
  assert.equal(counts.get("free_food"), 1);
});

test("filtered event pagination replaces client id-search backfill", () => {
  const data = read("src/lib/events/index.ts");
  const route = read("src/app/api/events/route.ts");
  const api = read("src/lib/events/api.ts");
  const navigation = read("src/components/events/useEventFeedNavigation.ts");
  const browser = read("src/components/events/EventsBrowser.tsx");

  assert.match(data, /filterEventSource/);
  assert.match(data, /function hasEventPageFilters/);
  assert.match(data, /withDbRetry\("filtered events"/);
  assert.match(route, /query: searchParams\.get\("q"\) \?\? ""/);
  assert.match(route, /category: coerceCategoryParam\(searchParams\.get\("cat"\)\)/);
  assert.match(route, /dayWindow: coerceDayWindowParam\(searchParams\.get\("when"\)\)/);
  assert.match(api, /params\.set\("q", filters\.query\.trim\(\)\)/);
  assert.match(api, /params\.set\("cat", filters\.category\)/);
  assert.match(api, /params\.set\("when", filters\.dayWindow\)/);
  assert.match(browser, /const feedFilters = useMemo/);
  assert.match(navigation, /fetchEventsPage\(nextOffset, undefined, feedFilters\)/);

  assert.doesNotMatch(data, /getEventsByIds/);
  assert.doesNotMatch(data, /EVENTS_BY_IDS_LIMIT/);
  assert.doesNotMatch(route, /searchParams\.get\("ids"\)/);
  assert.doesNotMatch(api, /fetchEventsByIds/);
  assert.doesNotMatch(browser, /useEventSearchBackfill/);
  assert.doesNotMatch(browser, /feedHasMore/);
});
