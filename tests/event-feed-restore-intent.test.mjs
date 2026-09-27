import assert from "node:assert/strict";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const { deriveRestoreIntent } = await importTsModule(
  "src/lib/events/feed-restore.ts"
);

function event(id) {
  return { id };
}

// A feed resumes after its last loaded event.
const after = (id) => ({ startsAt: "2026-05-20T18:30:00.000-07:00", id });

function snapshot(overrides = {}) {
  return {
    path: "/events",
    category: "all",
    query: "",
    dayWindow: "all",
    events: [event("event-1")],
    hasMore: true,
    cursor: after("event-1"),
    loadedCount: 1,
    ...overrides,
  };
}

function returnScroll(overrides = {}) {
  return {
    path: "/events",
    scrollY: 200,
    detailPath: "/events/target",
    ...overrides,
  };
}

test("snapshot eventId wins and pulls eventTop/loadedCount from a matching return target", () => {
  const intent = deriveRestoreIntent(
    snapshot({ eventId: "a", eventTop: 10, loadedCount: 5 }),
    returnScroll({ eventId: "a", eventTop: 99, loadedCount: 7 }),
    [],
    false,
    null
  );

  assert.equal(intent.kind, "card");
  assert.equal(intent.eventId, "a");
  assert.equal(intent.eventTop, 99);
  assert.equal(intent.loadedCount, 7);
  assert.deepEqual(
    intent.events.map((ev) => ev.id),
    ["event-1"]
  );
  assert.equal(intent.hasMore, true);
  assert.deepEqual(intent.cursor, after("event-1"));
});

test("snapshot eventId falls back to its own eventTop/loadedCount when the return target is for a different card", () => {
  const intent = deriveRestoreIntent(
    snapshot({ eventId: "a", eventTop: 10, loadedCount: 5 }),
    returnScroll({ eventId: "b", eventTop: 99, loadedCount: 7 }),
    [],
    false,
    null
  );

  assert.equal(intent.kind, "card");
  assert.equal(intent.eventId, "a");
  assert.equal(intent.eventTop, 10);
  assert.equal(intent.loadedCount, 5);
});

test("return target eventId is used when the snapshot has no eventId, with pagination from the snapshot", () => {
  const intent = deriveRestoreIntent(
    snapshot({ events: [event("event-1")], hasMore: false, cursor: after("event-30") }),
    returnScroll({ eventId: "target", eventTop: 20, loadedCount: 3 }),
    [event("current")],
    true,
    after("current")
  );

  assert.equal(intent.kind, "card");
  assert.equal(intent.eventId, "target");
  assert.equal(intent.eventTop, 20);
  assert.equal(intent.loadedCount, 3);
  assert.deepEqual(
    intent.events.map((ev) => ev.id),
    ["event-1"]
  );
  assert.equal(intent.hasMore, false);
  assert.deepEqual(intent.cursor, after("event-30"));
});

test("return target eventId falls back to current pagination when there is no snapshot", () => {
  const intent = deriveRestoreIntent(
    null,
    returnScroll({ eventId: "target", eventTop: 20, loadedCount: 3 }),
    [event("current")],
    true,
    after("current")
  );

  assert.equal(intent.kind, "card");
  assert.equal(intent.eventId, "target");
  assert.deepEqual(
    intent.events.map((ev) => ev.id),
    ["current"]
  );
  assert.equal(intent.hasMore, true);
  assert.deepEqual(intent.cursor, after("current"));
});

test("a return scroll with no eventId yields a plain scrollY intent", () => {
  const intent = deriveRestoreIntent(
    null,
    returnScroll({ scrollY: 333 }),
    [],
    false,
    null
  );

  assert.deepEqual(intent, { kind: "scrollY", scrollY: 333 });
});

test("no snapshot and no return scroll yields a none intent", () => {
  const intent = deriveRestoreIntent(null, null, [], false, null);

  assert.deepEqual(intent, { kind: "none" });
});
