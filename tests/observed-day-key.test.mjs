import assert from "node:assert/strict";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const {
  SCROLL_SPY_OFFSET_PX,
  resolveObservedDayKey,
} = await importTsModule("src/lib/events/observed-day-key.ts");

test("observed day stays on the first day while the viewport is above the feed", () => {
  const observed = resolveObservedDayKey({
    dayKeys: ["2026-05-23", "2026-05-24"],
    headerTopByKey: new Map([
      ["2026-05-23", SCROLL_SPY_OFFSET_PX + 320],
      ["2026-05-24", SCROLL_SPY_OFFSET_PX + 460],
    ]),
    sectionBottomByKey: new Map([
      ["2026-05-23", SCROLL_SPY_OFFSET_PX + 420],
      ["2026-05-24", SCROLL_SPY_OFFSET_PX + 900],
    ]),
    viewportHeight: 720,
  });

  assert.equal(observed, "2026-05-23");
});

test("observed day can advance after the first day scrolls past the spy line", () => {
  const observed = resolveObservedDayKey({
    dayKeys: ["2026-05-23", "2026-05-24"],
    headerTopByKey: new Map([
      ["2026-05-23", SCROLL_SPY_OFFSET_PX - 360],
      ["2026-05-24", SCROLL_SPY_OFFSET_PX + 20],
    ]),
    sectionBottomByKey: new Map([
      ["2026-05-23", SCROLL_SPY_OFFSET_PX - 10],
      ["2026-05-24", SCROLL_SPY_OFFSET_PX + 500],
    ]),
    viewportHeight: 720,
  });

  assert.equal(observed, "2026-05-24");
});
