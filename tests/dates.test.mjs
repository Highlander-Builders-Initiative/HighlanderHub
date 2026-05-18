import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";

test("campus date helpers stay aligned across runtime timezones", () => {
  const result = spawnSync(
    process.execPath,
    [
      "--experimental-strip-types",
      "--input-type=module",
      "--eval",
      `
        import { mock } from "node:test";
        mock.timers.enable({ apis: ["Date"], now: new Date("2026-05-18T08:00:00Z") });
        const dates = await import("./src/lib/dates.ts");
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
