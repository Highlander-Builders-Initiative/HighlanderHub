import assert from "node:assert/strict";
import { test } from "node:test";

test("campus date helpers stay aligned across runtime timezones", async () => {
  const previousTz = process.env.TZ;
  process.env.TZ = "UTC";

  try {
    const dates = await import("../src/lib/dates.ts");

    const lateEveningUtc = "2026-05-19T06:30:00Z";
    assert.equal(dates.pacificDayKey(lateEveningUtc), "2026-05-18");
    assert.equal(dates.formatDay(lateEveningUtc), "Monday, May 18");
    assert.equal(dates.formatDayShort(lateEveningUtc), "Mon, May 18");
    assert.equal(dates.relativeDay(lateEveningUtc), "Today");
    assert.equal(dates.formatTime(lateEveningUtc), "11:30pm");
  } finally {
    if (previousTz === undefined) {
      delete process.env.TZ;
    } else {
      process.env.TZ = previousTz;
    }
  }
});
