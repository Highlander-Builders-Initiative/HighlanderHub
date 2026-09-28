import test from "node:test";
import assert from "node:assert/strict";

import { importTsModule } from "./helpers/import-ts-module.mjs";

const { buildIcsContent, calendarHref, icsHref } = await importTsModule(
  "src/lib/events/actions.ts"
);

const event = {
  id: "evt 1",
  title: "Pizza, Planning; Night",
  description: "Line one\nLine two",
  startsAt: "2026-06-01T10:00:00.000-07:00",
  location: "HUB 302",
  host: "ACM",
  category: "get_involved",
  contentKind: "student_event",
  tags: [],
  source: "manual",
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

test("a date-only deadline becomes an all-day entry on its due date, not a day opening at midnight", () => {
  // AEPi's "by Sep. 27th": stored as Pacific midnight to the midnight after.
  const deadline = {
    ...event,
    contentKind: "student_deadline",
    startsAt: "2026-09-27T07:00:00+00:00",
    endsAt: "2026-09-28T07:00:00+00:00",
  };
  const ics = buildIcsContent(deadline, new Date("2026-09-20T12:00:00.000Z"));
  assert.match(ics, /\r\nDTSTART;VALUE=DATE:20260927\r\n/);
  assert.match(ics, /\r\nDTEND;VALUE=DATE:20260928\r\n/);
  assert.equal(new URL(calendarHref(deadline)).searchParams.get("dates"), "20260927/20260928");

  // Winter offset, and a multi-day all-day event, whose end stays exclusive.
  const winter = { ...deadline, startsAt: "2027-01-18T08:00:00Z", endsAt: "2027-01-19T08:00:00Z" };
  assert.equal(new URL(calendarHref(winter)).searchParams.get("dates"), "20270118/20270119");
  const fair = { ...event, startsAt: "2026-10-31T07:00:00Z", endsAt: "2026-11-02T08:00:00Z" };
  assert.equal(new URL(calendarHref(fair)).searchParams.get("dates"), "20261031/20261102");
});

test("timed entries keep their clock times", () => {
  // Panhellenic's "Sunday 9/27 at 11:59 PM": the entry opens at the cutoff.
  const deadline = { ...event, contentKind: "student_deadline", startsAt: "2026-09-28T06:59:00+00:00" };
  const ics = buildIcsContent(deadline, new Date("2026-09-20T12:00:00.000Z"));
  assert.match(ics, /\r\nDTSTART:20260928T065900Z\r\n/);
  assert.equal(new URL(calendarHref(deadline)).searchParams.get("dates"), "20260928T065900Z/20260928T075900Z");
  const evening = { ...event, startsAt: "2026-09-24T18:30:00-07:00", endsAt: "2026-09-24T20:00:00-07:00" };
  assert.equal(new URL(calendarHref(evening)).searchParams.get("dates"), "20260925T013000Z/20260925T030000Z");
});
