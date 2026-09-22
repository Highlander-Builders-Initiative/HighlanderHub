import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";

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
            { contentKind: "student_deadline", startsAt: "2026-09-22T07:00:00Z", endsAt: "2026-09-23T07:00:00Z" },
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
    // A deadline at midnight keeps its cutoff time; it is never "All day".
    timeLabels: [
      ["7:00 PM", "7:00pm – 9:00pm"],
      ["All day", "All day"],
      ["12:00 AM", "12:00am"],
    ],
  });
});
