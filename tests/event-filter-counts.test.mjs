import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

function makeEvent(id, category, overrides = {}) {
  return {
    id,
    title: id,
    description: "Event description",
    startsAt: "2026-05-25T18:30:00.000-07:00",
    location: "HUB",
    host: "QA",
    category,
    tags: [],
    source: "manual",
    rsvpRequired: false,
    scrapedAt: "2026-05-18T12:00:00.000Z",
    ...overrides,
  };
}

test("event category badge counts come from the full count source, not the loaded page", async () => {
  const { useEventFeedFilters } = await importTsModule(
    "src/components/events/useEventFeedFilters.ts"
  );
  let result;

  function Harness() {
    result = useEventFeedFilters({
      loadedEvents: [makeEvent("loaded-hangout", "hangout")],
      filterCountSource: [
        makeEvent("loaded-hangout", "hangout"),
        makeEvent("unloaded-hangout", "hangout"),
        makeEvent("unloaded-academic", "academic"),
      ],
      category: "all",
      query: "",
      dayWindow: "all",
      todayKey: "2026-05-23",
    });

    return React.createElement("pre", null, result.resultsLabel);
  }

  renderToStaticMarkup(React.createElement(Harness));

  assert.ok(result);
  assert.equal(result.filtered.length, 1);
  assert.equal(result.resultsLabel, "1 of 3 events loaded");
  assert.equal(result.counts.categories.get("all"), 3);
  assert.equal(result.counts.categories.get("hangout"), 2);
  assert.equal(result.counts.categories.get("academic"), 1);
});

test("event filter summary omits the total when every event is loaded", async () => {
  const { useEventFeedFilters } = await importTsModule(
    "src/components/events/useEventFeedFilters.ts"
  );
  let result;
  const hangoutEvent = makeEvent("loaded-hangout", "hangout");

  function Harness() {
    result = useEventFeedFilters({
      loadedEvents: [hangoutEvent],
      filterCountSource: [hangoutEvent],
      category: "all",
      query: "",
      dayWindow: "all",
      todayKey: "2026-05-23",
    });

    return React.createElement("pre", null, result.resultsLabel);
  }

  renderToStaticMarkup(React.createElement(Harness));

  assert.ok(result);
  assert.equal(result.resultsLabel, "1 event loaded");
});

test("event category badges use a full-feed count source outside pagination", () => {
  const layout = read("src/app/events/layout.tsx");
  const feedData = read("src/components/events/EventsFeedData.tsx");
  const browser = read("src/components/events/EventsBrowser.tsx");
  const filters = read("src/components/events/useEventFeedFilters.ts");
  const data = read("src/lib/events/index.ts");

  assert.match(data, /export const getEventFilterCountSource = cachePublicRead\(/);
  assert.match(
    data,
    /\.select\("id,title,description,starts_at,sort_at,location,host,host_handle,hosts,category,content_kind,tags,has_free_food"\)/
  );
  assert.match(layout, /getEventFilterCountSource/);
  assert.match(layout, /filterCountSource: shareCalendarEvents\(calendarEvents, countSource\)/);
  assert.match(feedData, /filterCountSource: EventFilterCountSource\[\]/);
  assert.match(browser, /filterCountSource,/);
  assert.match(filters, /filterCountSource: EventFilterCountSource\[\]/);
  assert.match(filters, /countEventFacets\(filterCountSource, filters/);
  assert.doesNotMatch(
    filters,
    /map\.set\("all", filteredExceptCategory\.length\)/
  );
});
