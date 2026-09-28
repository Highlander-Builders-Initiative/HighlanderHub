import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

test("a deadline reads as when it is due, as the database orders it", async (t) => {
  // Sunday Sep 27, 9 PM Pacific.
  t.mock.timers.enable({ apis: ["Date"], now: new Date("2026-09-28T04:00:00Z") });
  const { eventRowToCampusEvent } = await importTsModule("src/lib/events/map-event-row.ts");
  const { eventTimeLabel, pacificDayKey, relativeDay } = await importTsModule("src/lib/dates.ts");
  const { eventListLinkLabel } = await importTsModule("src/lib/events/a11y.ts");
  const base = {
    title: "Application Deadline", content_kind: "student_deadline", category: "get_involved",
    host: "Club", host_handle: "club", hosts: [],
  };
  // Live rows as read back: "by Sep. 27th" (date only; sort_at is 11:59 PM
  // that day, see tests/integration/event-sort-at) and "Sunday 9/27 at 11:59 PM".
  const dateOnly = eventRowToCampusEvent({
    ...base, id: "ig_aepi_ucr_p3990583520376565404", starts_at: "2026-09-27T07:00:00+00:00",
    ends_at: "2026-09-28T07:00:00+00:00", sort_at: "2026-09-28T06:59:00+00:00", all_day: true,
  });
  const timed = eventRowToCampusEvent({
    ...base, id: "ig_ucrpanhellenic_p3994334049968160459", starts_at: "2026-09-28T06:59:00+00:00",
    ends_at: null, sort_at: "2026-09-28T06:59:00+00:00", all_day: false,
  });
  // A printed "12:00 AM" cutoff is a real midnight, filed under the day it opens.
  const midnight = { ...timed, startsAt: "2026-09-28T07:00:00Z", sortAt: "2026-09-28T07:00:00Z" };

  const labels = (event) => [eventTimeLabel(event, "start"), eventTimeLabel(event, "span")];
  assert.deepEqual(labels(dateOnly), ["11:59 PM", "11:59pm"]);
  assert.deepEqual(labels(timed), ["11:59 PM", "11:59pm"]);
  assert.deepEqual(labels(midnight), ["12:00 AM", "12:00am"]);
  assert.deepEqual([dateOnly, timed, midnight].map((event) => pacificDayKey(event.startsAt)),
    ["2026-09-27", "2026-09-27", "2026-09-28"]);
  assert.deepEqual([dateOnly, timed, midnight].map((event) => relativeDay(event.startsAt)),
    ["Today", "Today", "Tomorrow"]);
  assert.equal(eventListLinkLabel(dateOnly), "Deadline: Application Deadline, due Today at 11:59 PM");
  assert.equal(eventListLinkLabel(timed), "Deadline: Application Deadline, due Today at 11:59 PM");
  assert.equal(eventListLinkLabel(midnight), "Deadline: Application Deadline, due Tomorrow at 12:00 AM");
});

test("campus date helpers stay aligned across runtime timezones", () => {
  const result = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "--eval",
      `
        import { importTsModule } from "./tests/helpers/import-ts-module.mjs";
        import { mock } from "node:test";
        mock.timers.enable({ apis: ["Date"], now: new Date("2026-05-18T08:00:00Z") });
        const dates = await importTsModule("src/lib/dates.ts");
        const iso = "2026-05-19T06:30:00Z";
        console.log(JSON.stringify({
          dayKey: dates.pacificDayKey(iso),
          day: dates.formatDay(iso),
          shortDay: dates.formatDayShort(iso),
          relative: dates.relativeDay(iso),
          time: dates.formatTime(iso)
        }));
      `,
    ],
    {
      cwd: process.cwd(),
      env: { ...process.env, TZ: "UTC" },
      encoding: "utf8",
    }
  );

  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout.trim()), {
    dayKey: "2026-05-18",
    day: "Monday, May 18",
    shortDay: "Mon, May 18",
    relative: "Today",
    time: "11:30pm",
  });
});

test("Pacific day-key helpers do calendar math outside the browser timezone", () => {
  const result = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "--eval",
      `
        import { importTsModule } from "./tests/helpers/import-ts-module.mjs";
        import { mock } from "node:test";
        mock.timers.enable({ apis: ["Date"], now: new Date("2026-05-20T02:00:00Z") });
        const dates = await importTsModule("src/lib/dates.ts");
        console.log(JSON.stringify({
          todayKey: dates.pacificTodayKey(),
          monthStart: dates.startOfPacificMonthKey("2026-05-19"),
          nextDay: dates.addPacificDays("2026-05-19", 1),
          nextMonth: dates.addPacificMonths("2026-12-01", 1),
          grid: dates.pacificCalendarGridRange("2026-05-01"),
          weekday: dates.pacificWeekdayIndex("2026-05-19"),
          dayOfMonth: dates.pacificDayOfMonth("2026-05-19"),
          monthLabel: dates.formatPacificMonth("2026-05-01"),
          dayLabel: dates.formatPacificDayKey("2026-05-19"),
          headings: ["2026-05-19", "2026-05-20", "2026-05-21", "2027-01-05"].map(
            (key) => dates.pacificDayHeading(key, dates.pacificTodayKey())
          ),
          allDay: [
            ["2026-09-22T07:00:00Z", "2026-09-23T07:00:00Z"],
            ["2026-09-28T07:00:00Z", "2026-10-04T07:00:00Z"],
            ["2026-10-31T07:00:00Z", "2026-11-02T08:00:00Z"],
            ["2026-09-22T07:00:00Z", undefined],
            ["2026-09-22T07:00:00Z", "2026-09-22T09:00:00Z"],
          ].map(([start, end]) => dates.formatAllDay(start, end)),
          range: dates.formatTimeRange("2026-09-22T07:00:00Z", "2026-09-23T07:00:00Z"),
          timeLabels: [
            { startsAt: "2026-09-23T02:00:00Z", endsAt: "2026-09-23T04:00:00Z" },
            { startsAt: "2026-09-22T07:00:00Z", endsAt: "2026-09-23T07:00:00Z" },
            { contentKind: "student_deadline", startsAt: "2026-09-22T07:00:00Z", endsAt: "2026-09-23T07:00:00Z", sortAt: "2026-09-23T06:59:00Z" },
          ].map((event) => [dates.eventTimeLabel(event, "start"), dates.eventTimeLabel(event, "span")])
        }));
      `,
    ],
    {
      cwd: process.cwd(),
      env: { ...process.env, TZ: "Asia/Tokyo" },
      encoding: "utf8",
    }
  );

  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout.trim()), {
    todayKey: "2026-05-19",
    monthStart: "2026-05-01",
    nextDay: "2026-05-20",
    nextMonth: "2027-01-01",
    grid: { start: "2026-04-26", end: "2026-06-06" },
    weekday: 2,
    dayOfMonth: 19,
    monthLabel: "May 2026",
    dayLabel: "Tuesday, May 19",
    headings: [
      { label: "Today", weekday: "Tuesday" },
      { label: "Tomorrow", weekday: "Wednesday" },
      { label: "May 21", weekday: "Thursday" },
      { label: "Jan 5, 2027", weekday: "Tuesday" },
    ],
    // Midnight-to-midnight Pacific is all day, across a DST change too;
    // a midnight start without a midnight end keeps its clock time.
    allDay: ["All day", "All day through Oct 3", "All day through Nov 1", null, null],
    range: "All day",
    // A date-only deadline is due by the end of its day; it is never "All day".
    timeLabels: [
      ["7:00 PM", "7:00pm – 9:00pm"],
      ["All day", "All day"],
      ["11:59 PM", "11:59pm"],
    ],
  });
});
