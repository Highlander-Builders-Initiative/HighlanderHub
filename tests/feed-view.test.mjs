import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const { coerceFeedView, FEED_VIEW_COOKIE } = await importTsModule(
  "src/components/events/events-filters.ts"
);
const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("the feed-view cookie only ever widens to compact on an exact match", () => {
  assert.equal(coerceFeedView("compact"), "compact");
  assert.equal(coerceFeedView("cards"), "cards");
  assert.equal(coerceFeedView(undefined), "cards");
  assert.equal(coerceFeedView("COMPACT"), "cards");
  assert.equal(coerceFeedView("list"), "cards");
});

test("the saved view is read on the server and is desktop-only on the client", () => {
  const page = read("src/app/events/page.tsx");
  const browser = read("src/components/events/EventsBrowser.tsx");
  const feed = read("src/components/events/EventsFeedColumn.tsx");

  assert.equal(FEED_VIEW_COOKIE, "hh_feed_view");
  assert.match(page, /coerceFeedView\(\(await cookies\(\)\)\.get\(FEED_VIEW_COOKIE\)\?\.value\)/);
  assert.match(page, /initialView=\{initialView\}/);
  assert.match(browser, /const listView: FeedView = isDesktop \? view : "cards"/);
  assert.match(browser, /path=\/events/);
  assert.match(feed, /<EventFeedViewToggle[\s\S]*className="hidden lg:flex"/);
  assert.match(feed, /<EventCompactRow /);
});

test("compact rows stay real links with the card's open behavior", () => {
  const card = read("src/components/events/EventCard.tsx");

  // Both shapes: crawlable link, no list scroll, feed-return anchor.
  assert.equal(card.match(/href=\{href\}/g)?.length, 2);
  assert.equal(card.match(/scroll=\{false\}/g)?.length, 2);
  assert.equal(card.match(/data-event-id=\{event\.id\}/g)?.length, 2);
  assert.equal(card.match(/aria-label=\{eventListLinkLabel\(event\)\}/g)?.length, 2);
  assert.match(card, /tag\.kind !== "category"/);
  // The row's focus ring sits inside it, not under its neighbours.
  assert.match(card, /focus-visible:!outline-offset-\[-3px\]/);
});

test("the unfiltered count is announced, not shown", () => {
  const feed = read("src/components/events/EventsFeedColumn.tsx");

  assert.match(feed, /className=\{hasActiveFilters \? "mb-6 text-sm text-muted" : "sr-only"\}/);
  assert.doesNotMatch(feed, /formatPacificDayKey/);
});
