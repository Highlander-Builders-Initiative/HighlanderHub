import assert from "node:assert/strict";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const { campusDaypart } = await importTsModule("src/lib/daylight.ts");

// Riverside sunrise/sunset (UTC), from the astral library.
const days = [
  ["2026-06-21T12:38:51Z", "2026-06-22T03:03:33Z"], // 5:39am / 8:04pm PDT
  ["2026-11-01T14:09:08Z", "2026-11-02T00:56:06Z"], // 6:09am / 4:56pm PST
  ["2026-12-21T14:51:03Z", "2026-12-22T00:44:02Z"], // 6:51am / 4:44pm PST
];
const MIN = 60 * 1000;
const at = (iso, minutes) => new Date(Date.parse(iso) + minutes * MIN);

test("the golden hour around sunrise is golden", () => {
  for (const [sunrise] of days) {
    assert.equal(campusDaypart(at(sunrise, -45)), "night", `well before ${sunrise}`);
    assert.equal(campusDaypart(at(sunrise, -10)), "golden", `just before ${sunrise}`);
    assert.equal(campusDaypart(at(sunrise, 15)), "golden", `after ${sunrise}`);
    assert.equal(campusDaypart(at(sunrise, 75)), "day", `well after ${sunrise}`);
  }
});

test("the golden hour around sunset is golden", () => {
  for (const [, sunset] of days) {
    assert.equal(campusDaypart(at(sunset, -75)), "day", `well before ${sunset}`);
    assert.equal(campusDaypart(at(sunset, -15)), "golden", `before ${sunset}`);
    assert.equal(campusDaypart(at(sunset, 10)), "golden", `just after ${sunset}`);
    assert.equal(campusDaypart(at(sunset, 45)), "night", `well after ${sunset}`);
  }
});

test("the daypart follows the season, not the clock", () => {
  // 7:30pm Pacific: golden in June, long dark in December.
  assert.equal(campusDaypart(new Date("2026-06-22T02:30:00Z")), "golden");
  assert.equal(campusDaypart(new Date("2026-12-22T03:30:00Z")), "night");
  // Local midnight and noon.
  assert.equal(campusDaypart(new Date("2026-09-23T07:00:00Z")), "night");
  assert.equal(campusDaypart(new Date("2026-09-23T19:00:00Z")), "day");
});
