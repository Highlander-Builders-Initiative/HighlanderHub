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
    sortAt: "2026-05-25T18:30:00.000-07:00",
    location: "HUB",
    host: "QA",
    hostHandle: null,
    category: "hangout",
    contentKind: "student_event",
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
      category: "get_involved",
      hasFreeFood: true,
    }),
    makeSource("food-social", {
      title: "Snack Hackathon Social",
      hasFreeFood: true,
    }),
    makeSource("later-hack", {
      title: "Fall Hackathon",
      startsAt: "2026-06-05T18:30:00.000-07:00",
      sortAt: "2026-06-05T18:30:00.000-07:00",
    }),
    makeSource("movie", { title: "Movie Night" }),
  ];

  assert.deepEqual(
    filterEventSource(source, {
      category: "all",
      freeFood: true,
      dayWindow: "week",
      todayKey: "2026-05-25",
      normalizedQuery: "hackathon",
    }).map((event) => event.id),
    ["food-hack", "food-social"]
  );
  // Free food narrows the topic instead of replacing it.
  assert.deepEqual(
    filterEventSource(source, {
      category: "get_involved",
      freeFood: true,
      dayWindow: "all",
      todayKey: "2026-05-25",
      normalizedQuery: "",
    }).map((event) => event.id),
    ["food-hack"]
  );
});

test("each facet count applies every other filter", async () => {
  const { countEventFacets } = await importTsModule(
    "src/components/events/events-filters.ts"
  );
  const source = [
    makeSource("hangout"),
    makeSource("academic", { category: "academic" }),
    makeSource("food-flag", { category: "get_involved", hasFreeFood: true }),
    makeSource("faith-food", { hostHandle: "@aacfucriverside", hasFreeFood: true }),
    makeSource("deadline", { category: "other", contentKind: "student_deadline" }),
  ];
  const base = { category: "all", dayWindow: "all", todayKey: "2026-05-25", normalizedQuery: "" };

  const counts = countEventFacets(source, base);
  assert.equal(counts.categories.get("all"), 5);
  assert.equal(counts.categories.get("hangout"), 2);
  assert.equal(counts.categories.get("academic"), 1);
  // An uncategorized event counts under All only.
  assert.equal(counts.categories.has("other"), false);
  assert.equal(counts.freeFood, 2);
  assert.equal(counts.deadlines, 1);
  assert.equal(counts.hostGroups.get("faith"), 1);

  // With Free food on, the topics count food events; its own count does not shrink.
  const withFood = countEventFacets(source, { ...base, freeFood: true });
  assert.equal(withFood.categories.get("all"), 2);
  assert.equal(withFood.categories.get("hangout"), 1);
  assert.equal(withFood.categories.get("get_involved"), 1);
  assert.equal(withFood.freeFood, 2);

  const hangout = countEventFacets(source, { ...base, category: "hangout" });
  assert.equal(hangout.freeFood, 1);
  assert.equal(hangout.hostGroups.get("faith"), 1);
  assert.equal(hangout.categories.get("academic"), 1);
});

test("feed URLs round-trip every filter and keep old topic links working", async () => {
  const { readEventFeedQuery, eventFeedSearchParams, eventsFeedHref } = await importTsModule(
    "src/components/events/events-filters.ts"
  );
  const read = (search) => {
    const params = new URLSearchParams(search);
    return readEventFeedQuery((key) => params.get(key));
  };

  const full = read("cat=hangout&q=boba&when=week&food=1&deadlines=1&host=culture");
  assert.deepEqual(full, {
    query: "boba", category: "hangout", dayWindow: "week",
    freeFood: true, deadlines: true, hostGroup: "culture",
  });
  assert.equal(
    eventFeedSearchParams(full).toString(),
    "cat=hangout&q=boba&when=week&food=1&deadlines=1&host=culture"
  );

  assert.equal(read("cat=social").category, "hangout");
  assert.equal(read("cat=club").category, "get_involved");
  assert.equal(read("cat=community").category, "volunteering");
  assert.deepEqual(
    [read("cat=free_food").category, read("cat=free_food").freeFood],
    ["all", true]
  );
  assert.equal(read("cat=other").category, "all");
  assert.equal(read("host=nope").hostGroup, "all");
  assert.equal(eventsFeedHref({ freeFood: true }), "/events?food=1");
  assert.equal(eventsFeedHref({}), "/events");
});

test("Hosted by groups every host of a listing by its directory type", async () => {
  const { matchesHostGroup } = await importTsModule("src/lib/host-groups.ts");

  assert.equal(matchesHostGroup({ hostHandle: "ucrcsa" }, "culture"), true);
  // Ethnic student programs are campus offices listed with the groups they serve.
  assert.equal(matchesHostGroup({ hostHandle: "aspucr" }, "culture"), true);
  assert.equal(matchesHostGroup({ hostHandle: "aspucr" }, "campus"), false);
  assert.equal(matchesHostGroup({ hostHandle: "ucrcareercenter" }, "campus"), true);
  assert.equal(matchesHostGroup({ hostHandle: "@AACFUCRIVERSIDE" }, "faith"), true);
  assert.equal(
    matchesHostGroup(
      { hostHandle: "acm_ucr", hosts: [{ host: "ACM", hostHandle: "acm_ucr" }, { host: "CSA", hostHandle: "ucrcsa" }] },
      "culture"
    ),
    true
  );
  assert.equal(matchesHostGroup({ hostHandle: "acm_ucr" }, "culture"), false);
  assert.equal(matchesHostGroup({ hostHandle: undefined }, "all"), true);
});

test("filtered event pagination replaces client id-search backfill", () => {
  const data = read("src/lib/events/index.ts");
  const route = read("src/app/api/events/route.ts");
  const api = read("src/lib/events/api.ts");
  const navigation = read("src/components/events/useEventFeedNavigation.ts");
  const browser = read("src/components/events/EventsBrowser.tsx");
  const filtersHook = read("src/components/events/useEventFeedFilters.ts");

  assert.match(data, /filterEventSource/);
  assert.match(data, /function hasEventPageFilters/);
  // The page, the route and the client share one reading of the feed URL.
  assert.match(route, /readEventFeedQuery\(\(key\) => searchParams\.get\(key\)\)/);
  assert.match(read("src/app/events/page.tsx"), /readEventFeedQuery\(/);
  assert.match(api, /const params = eventFeedSearchParams\(filters\)/);
  assert.match(browser, /const feedFilters = useMemo/);
  assert.match(navigation, /fetchEventsPage\(cursor, undefined, requested\)/);
  assert.match(
    filtersHook,
    /useMemo\(\(\) => Array.from\(grouped\.keys\(\)\), \[grouped\]\)/
  );

  assert.doesNotMatch(data, /getEventsByIds/);
  assert.doesNotMatch(data, /EVENTS_BY_IDS_LIMIT/);
  assert.doesNotMatch(route, /searchParams\.get\("ids"\)/);
  assert.doesNotMatch(api, /fetchEventsByIds/);
  assert.doesNotMatch(browser, /useEventSearchBackfill/);
  assert.doesNotMatch(browser, /feedHasMore/);
});

test("event feed queries compare by category, day window, and trimmed query", async () => {
  const { eventFeedQueriesEqual } = await importTsModule(
    "src/components/events/events-filters.ts"
  );

  assert.equal(
    eventFeedQueriesEqual(
      { category: "sports", query: "  club ", dayWindow: "week" },
      { category: "sports", query: "club", dayWindow: "week" }
    ),
    true
  );
  assert.equal(
    eventFeedQueriesEqual(
      { category: "sports", query: "", dayWindow: "all" },
      { category: "all", query: "", dayWindow: "all" }
    ),
    false
  );
  const base = { category: "all", query: "", dayWindow: "all", freeFood: false, deadlines: false, hostGroup: "all" };
  for (const change of [{ freeFood: true }, { deadlines: true }, { hostGroup: "faith" }]) {
    assert.equal(eventFeedQueriesEqual(base, { ...base, ...change }), false);
  }
});
