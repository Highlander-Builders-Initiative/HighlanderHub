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

test("the saved view is read on the server and offered at every width", () => {
  const page = read("src/app/events/page.tsx");
  const browser = read("src/components/events/EventsBrowser.tsx");
  const feed = read("src/components/events/EventsFeedColumn.tsx");

  assert.equal(FEED_VIEW_COOKIE, "hh_feed_view");
  assert.match(page, /coerceFeedView\(\(await cookies\(\)\)\.get\(FEED_VIEW_COOKIE\)\?\.value\)/);
  assert.match(page, /initialView=\{initialView\}/);
  assert.match(browser, /path=\/events/);
  // Phones get the compact view too: no breakpoint gate on the list or toggle.
  assert.doesNotMatch(browser, /matchMedia/);
  assert.match(feed, /<EventFeedViewToggle/);
  assert.doesNotMatch(feed, /<EventFeedViewToggle[^>]*className="hidden/);
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

test("compact rows restack for phones instead of hiding", () => {
  const card = read("src/components/events/EventCard.tsx");

  // Phone grid: time + where, title, hosts + tags beside the thumbnail.
  assert.match(card, /\[grid-template-areas:'thumb_time_loc_loc'_'thumb_title_title_title'_'thumb_host_host_tags'\]/);
  assert.match(card, /lg:\[grid-template-areas:'thumb_time_main_aside'\]/);
  assert.match(card, /contents lg:block/);
  assert.match(card, /contents lg:flex/);
});

test("the event detail reads in the feed's language", () => {
  const view = read("src/components/events/EventDetailView.tsx");
  const modal = read("src/components/events/EventModal.tsx");

  // No flyer-colored wash, no boxed tiles, no card nested in the panel.
  assert.doesNotMatch(view, /blur-3xl/);
  assert.doesNotMatch(view, /TILE_CLASS/);
  assert.doesNotMatch(view, /rounded-xl border border-ink\/15 bg-canvas p-5/);
  assert.doesNotMatch(view, /shadow-card/);
  // The card's byline, with club pictures.
  assert.match(view, /<HostAvatars hosts=\{hosts\} size=\{20\} \/>/);
  // An event without a caption or tags shows no empty "About".
  assert.match(view, /\{hasAbout && \(/);
  // Close control is the neutral fill, not an outlined circle.
  assert.match(modal, /rounded-full bg-ink\/\[0\.06\]/);
});

test("the desktop bar names the day in view at its left, past the first heading", () => {
  const hook = read("src/components/events/useObservedDayKey.ts");
  const feed = read("src/components/events/EventsFeedColumn.tsx");
  const browser = read("src/components/events/EventsBrowser.tsx");

  // Keyed to the first heading and the spy line, so the label never blinks
  // out at a day boundary and always names the day the calendar marks.
  assert.match(hook, /dayHeaderRefs\.current\.get\(dayKeys\[0\]\)/);
  assert.match(hook, /getBoundingClientRect\(\)\.top <= SCROLL_SPY_OFFSET_PX/);
  assert.match(browser, /showObservedDay=\{pastFirstDayHeading\}/);
  assert.match(browser, /selectedKey=\{observedDayKey\}/);
  // At the capsule's left, where the eye starts a row, not its right end.
  assert.ok(
    feed.indexOf("data-observed-day") < feed.indexOf("<EventSearchBox"),
    "the day sits before the search field"
  );
  // Desktop only, silent for screen readers, and grown in (0fr to 1fr)
  // rather than holding an empty slot.
  assert.match(feed, /aria-hidden\s+data-observed-day=\{observedDayKey\}/);
  assert.match(
    feed,
    /lg:grid \$\{\s*showObservedDay \? "grid-cols-\[1fr\] opacity-100" : "grid-cols-\[0fr\] opacity-0"/
  );
  // At its own width, 20px in, never cut off: the field moves over with it.
  assert.match(feed, /<span className="ml-1 shrink-0 whitespace-nowrap /);
  assert.doesNotMatch(feed, /data-observed-day[\s\S]{0,900}(truncate|min-w-\[)/);
});

test("the view toggle is two named icons", () => {
  const toggle = read("src/components/events/EventFeedViewToggle.tsx");

  // Icon buttons, named for screen readers and on hover, no visible label.
  assert.match(toggle, /aria-label=\{v\.label\}/);
  assert.match(toggle, /title=\{v\.label\}/);
  assert.match(toggle, /aria-pressed=\{active\}/);
  assert.doesNotMatch(toggle, />\s*\{v\.label\}\s*</);
});

test("the Topics highlight wears the hovered or selected category's color", () => {
  const filter = read("src/components/events/EventCategoryFilter.tsx");

  assert.match(filter, /CATEGORY_PILL\[value as EventCategory\]\.highlight/);
  assert.match(filter, /className=\{\(id\) => `rounded-xl \$\{highlightClass/);
  assert.match(filter, /enableHover/);
});
