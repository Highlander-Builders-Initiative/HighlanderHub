import test from "node:test";
import assert from "node:assert/strict";

import { importTsModule } from "./helpers/import-ts-module.mjs";

const { SAVED_EVENTS_KEY, parseSavedIds, serializeSavedIds, toggleSavedId } =
  await importTsModule("src/lib/saved-events.ts");

test("SAVED_EVENTS_KEY is versioned", () => {
  assert.equal(SAVED_EVENTS_KEY, "hh:saved-events:v1");
});

test("parseSavedIds returns [] for empty or malformed input", () => {
  assert.deepEqual(parseSavedIds(null), []);
  assert.deepEqual(parseSavedIds(""), []);
  assert.deepEqual(parseSavedIds("not json"), []);
  assert.deepEqual(parseSavedIds('{"a":1}'), []);
});

test("parseSavedIds keeps strings, drops non-strings, and dedupes", () => {
  assert.deepEqual(
    parseSavedIds(JSON.stringify(["a", "b", "a", 3, null, "c"])),
    ["a", "b", "c"]
  );
});

test("serializeSavedIds round-trips through parseSavedIds", () => {
  const ids = ["evt_1", "evt_2"];
  assert.deepEqual(parseSavedIds(serializeSavedIds(ids)), ids);
});

test("toggleSavedId adds to the front when absent", () => {
  assert.deepEqual(toggleSavedId(["a"], "b"), ["b", "a"]);
});

test("toggleSavedId removes when present", () => {
  assert.deepEqual(toggleSavedId(["a", "b", "c"], "b"), ["a", "c"]);
});
