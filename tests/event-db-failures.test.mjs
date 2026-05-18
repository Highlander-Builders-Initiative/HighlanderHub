import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const source = readFileSync(
  new URL("../src/lib/events.ts", import.meta.url),
  "utf8"
);

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("event queries do not turn Supabase errors into empty UI states", () => {
  assert.doesNotMatch(source, /if \(error\) \{\s*console\.error\("getEvents failed:"[\s\S]*?return \[\];\s*\}/);
  assert.doesNotMatch(source, /if \(error\) \{\s*console\.error\("getEventById failed:"[\s\S]*?return null;\s*\}/);
  assert.match(source, /throw new Error\(`Unable to load \$\{operation\}/);
  assert.match(source, /console\.error\(`\[events-db\] \$\{operation\} failed`/);
  assert.match(source, /console\.warn\(`\[events-db\] \$\{operation\} attempt \$\{attempt\} failed`/);
});

test("missing detail rows still use the not-found path", () => {
  assert.match(source, /if \(!data\) return null;/);
});

test("Supabase-backed event routes are request-time rendered", () => {
  assert.match(read("src/app/page.tsx"), /export const dynamic = "force-dynamic"/);
  assert.match(read("src/app/events/page.tsx"), /export const dynamic = "force-dynamic"/);
  assert.match(read("src/app/events/[id]/page.tsx"), /export const dynamic = "force-dynamic"/);
  assert.match(read("src/app/api/events/route.ts"), /export const dynamic = "force-dynamic"/);
});
