import assert from "node:assert/strict";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

function campusEvent(id, overrides = {}) {
  return {
    id,
    title: id,
    description: `${id} description`,
    startsAt: "2026-09-24T18:30:00.000-07:00",
    endsAt: undefined,
    location: "HUB",
    host: "QA Club",
    hostHandle: "qa",
    hosts: [{ host: "QA Club", hostHandle: "qa" }],
    category: "club",
    contentKind: "student_event",
    tags: ["rsvp"],
    source: "instagram",
    sourceUrl: undefined,
    imageUrl: `https://example.com/${id}.jpg`,
    hasFreeFood: false,
    rsvpRequired: false,
    rsvpUrl: undefined,
    scrapedAt: "2026-09-20T12:00:00.000Z",
    ...overrides,
  };
}

// The shape toEventFilterCountSource builds, in its key order.
function countEntry(event) {
  const { id, title, description, startsAt, location, host, hostHandle, hosts, category, tags, hasFreeFood } = event;
  return { id, title, description, startsAt, location, host, hostHandle, hosts, category, tags, hasFreeFood };
}

test("feed and count entries reuse the calendar's object for the same event", async () => {
  const { shareCalendarEvents } = await importTsModule("src/lib/events/share-calendar-events.ts");
  const calendar = [campusEvent("a"), campusEvent("b")];

  const shared = shareCalendarEvents(calendar, {
    events: [campusEvent("a"), campusEvent("outside-month")],
    filterCountSource: [countEntry(campusEvent("b")), countEntry(campusEvent("later"))],
  });

  assert.equal(shared.events[0], calendar[0]);
  assert.equal(shared.events[1].id, "outside-month");
  assert.equal(shared.filterCountSource[0], calendar[1]);
  assert.equal(shared.filterCountSource[1].id, "later");
});

test("entries that disagree with the calendar keep their own data", async () => {
  const { shareCalendarEvents } = await importTsModule("src/lib/events/share-calendar-events.ts");
  const calendar = [campusEvent("a"), campusEvent("b", { hostHandle: undefined, hosts: [{ host: "QA Club" }] })];
  // Cached separately, so one list can hold an edit the other has not seen.
  const editedPageEvent = campusEvent("a", { title: "Renamed" });
  const editedCount = countEntry(campusEvent("b"));

  const shared = shareCalendarEvents(calendar, {
    events: [editedPageEvent],
    filterCountSource: [editedCount],
  });

  assert.equal(shared.events[0], editedPageEvent);
  assert.equal(shared.filterCountSource[0], editedCount);
});
