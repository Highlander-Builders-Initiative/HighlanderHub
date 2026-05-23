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
          weekday: dates.pacificWeekdayIndex("2026-05-19"),
          dayOfMonth: dates.pacificDayOfMonth("2026-05-19"),
          monthLabel: dates.formatPacificMonth("2026-05-01"),
          dayLabel: dates.formatPacificDayKey("2026-05-19")
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
    weekday: 2,
    dayOfMonth: 19,
    monthLabel: "May 2026",
    dayLabel: "Tuesday, May 19",
  });
});

test("submit date chips use the campus day outside the browser timezone", () => {
  const result = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "--eval",
      `
        import { importTsModule } from "./tests/helpers/import-ts-module.mjs";
        import { mock } from "node:test";
        mock.timers.enable({ apis: ["Date"], now: new Date("2026-05-21T06:30:00Z") });
        const submitDates = await importTsModule("src/lib/submit-datetime.ts");
        console.log(JSON.stringify({
          today: submitDates.submitTodayDateInput(),
          tomorrow: submitDates.submitTomorrowDateInput(),
          friday: submitDates.submitUpcomingFridayDateInput(),
          chip: submitDates.formatSubmitChipDate("2026-05-22"),
          preview: submitDates.formatSubmitPreviewDateTime("2026-05-20T23:45"),
          end: submitDates.computeSubmitEndsAtLocal("2026-05-20T23:30", "1h", ""),
          endPreview: submitDates.formatSubmitPreviewTime("2026-05-21T00:30")
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
    today: "2026-05-20",
    tomorrow: "2026-05-21",
    friday: "2026-05-22",
    chip: "May 22",
    preview: "Wed, May 20 · 11:45 PM",
    end: "2026-05-21T00:30",
    endPreview: "12:30 AM",
  });
});
