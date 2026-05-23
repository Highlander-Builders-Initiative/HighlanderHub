import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const sourceFile = (path) => new URL(`../${path}`, import.meta.url);
const read = (path) => readFileSync(sourceFile(path), "utf8");

function event(id, startsAt) {
  return { id, startsAt };
}

test("event pages use deterministic ordering for offset pagination", () => {
  const source = read("src/lib/events/index.ts");

  assert.match(
    source,
    /\.order\("starts_at", \{ ascending: true \}\)\s*\.order\("id", \{ ascending: true \}\)\s*\.range\(from, to\)/
  );
});

test("merged event pages keep a stable order when start times tie", async () => {
  const { mergeUniqueEventsByStart } = await importTsModule(
    "src/lib/events/merge.ts"
  );

  const startsAt = "2026-05-25T18:00:00.000Z";
  const merged = mergeUniqueEventsByStart(
    [event("event-b", startsAt)],
    [event("event-a", startsAt), event("event-c", "2026-05-25T19:00:00.000Z")]
  );

  assert.deepEqual(
    merged.map((item) => item.id),
    ["event-a", "event-b", "event-c"]
  );
});
