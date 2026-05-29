import assert from "node:assert/strict";
import { existsSync, mkdirSync, readFileSync, symlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

function ensureTempNodeModules() {
  const outRoot = join(tmpdir(), "highlanderhub-ts-test");
  const target = join(outRoot, "node_modules");
  if (existsSync(target)) return;
  mkdirSync(outRoot, { recursive: true });
  symlinkSync(fileURLToPath(new URL("../node_modules", import.meta.url)), target);
}

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
    isFree: true,
    rsvpRequired: false,
    scrapedAt: "2026-05-18T12:00:00.000Z",
    ...overrides,
  };
}

test("event category badge counts come from the full count source, not the loaded page", async () => {
  ensureTempNodeModules();
  const { useEventFeedFilters } = await importTsModule(
    "src/components/events/useEventFeedFilters.ts"
  );
  let result;

  function Harness() {
    result = useEventFeedFilters({
      loadedEvents: [makeEvent("loaded-social", "social")],
      filterCountSource: [
        makeEvent("loaded-social", "social"),
        makeEvent("unloaded-social", "social"),
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
  assert.equal(result.counts.get("all"), 3);
  assert.equal(result.counts.get("social"), 2);
  assert.equal(result.counts.get("academic"), 1);
});

test("event filter summary omits the total when every event is loaded", async () => {
  ensureTempNodeModules();
  const { useEventFeedFilters } = await importTsModule(
    "src/components/events/useEventFeedFilters.ts"
  );
  let result;
  const socialEvent = makeEvent("loaded-social", "social");

  function Harness() {
    result = useEventFeedFilters({
      loadedEvents: [socialEvent],
      filterCountSource: [socialEvent],
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
  const page = read("src/app/events/page.tsx");
  const browser = read("src/components/events/EventsBrowser.tsx");
  const filters = read("src/components/events/useEventFeedFilters.ts");
  const data = read("src/lib/events/index.ts");

  assert.match(data, /export const getEventFilterCountSource = unstable_cache\(/);
  assert.match(
    data,
    /\.select\("id,title,description,starts_at,location,host,host_handle,category,tags"\)/
  );
  assert.match(data, /withDbRetry\("event filter counts"/);
  assert.match(page, /getEventFilterCountSource/);
  assert.match(page, /filterCountSource=\{filterCountSource\}/);
  assert.match(browser, /filterCountSource: EventFilterCountSource\[\]/);
  assert.match(browser, /filterCountSource,/);
  assert.match(filters, /filterCountSource: EventFilterCountSource\[\]/);
  assert.match(filters, /const countSourceExceptCategory = useMemo/);
  assert.match(filters, /map\.set\("all", countSourceExceptCategory\.length\)/);
  assert.doesNotMatch(
    filters,
    /map\.set\("all", filteredExceptCategory\.length\)/
  );
});
