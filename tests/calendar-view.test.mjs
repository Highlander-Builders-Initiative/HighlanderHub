import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const source = readFileSync(
  new URL("../src/components/events/CalendarView.tsx", import.meta.url),
  "utf8"
);

test("calendar view switches to a stacked mobile agenda before the grid layout", () => {
  assert.match(source, /sm:hidden/);
  assert.match(source, /hidden sm:block/);
  assert.match(source, /mobileAgendaDays/);
  assert.match(source, /aria-label=\{`Show events for \$\{formatDay/);
});
