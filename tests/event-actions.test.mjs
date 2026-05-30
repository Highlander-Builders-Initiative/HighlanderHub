import test from "node:test";
import assert from "node:assert/strict";

import { importTsModule } from "./helpers/import-ts-module.mjs";

const { buildIcsContent, icsHref } = await importTsModule(
  "src/lib/events/actions.ts"
);

const event = {
  id: "evt 1",
  title: "Pizza, Planning; Night",
  description: "Line one\nLine two",
  startsAt: "2026-06-01T10:00:00.000-07:00",
  location: "HUB 302",
  host: "ACM",
  category: "club",
  contentKind: "student_event",
  tags: [],
  source: "manual",
  isFree: true,
  rsvpRequired: false,
  scrapedAt: "2026-05-30T12:00:00.000Z",
};

test("icsHref points to the per-event calendar download route", () => {
  assert.equal(icsHref(event.id), "/events/evt%201/event.ics");
});

test("buildIcsContent emits escaped single-event calendar content", () => {
  const ics = buildIcsContent(event, new Date("2026-05-30T12:00:00.000Z"));

  assert.match(ics, /^BEGIN:VCALENDAR\r\nVERSION:2.0/);
  assert.match(ics, /UID:evt 1@highlanderhub\.app/);
  assert.match(ics, /DTSTAMP:20260530T120000Z/);
  assert.match(ics, /DTSTART:20260601T170000Z/);
  assert.match(ics, /DTEND:20260601T180000Z/);
  assert.match(ics, /SUMMARY:Pizza\\, Planning\\; Night/);
  assert.match(ics, /DESCRIPTION:Line one\\nLine two/);
  assert.match(ics, /LOCATION:HUB 302/);
  assert.match(ics, /\r\nEND:VCALENDAR\r\n$/);
});
