import assert from "node:assert/strict";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

function event(id) {
  return { id };
}

test("restoreEventsUntilTarget batches to the saved loaded count, then falls back to pages", async () => {
  const { restoreEventsUntilTarget } = await importTsModule(
    "src/lib/event-feed-restore.ts"
  );
  const calls = [];
  const pages = [
    {
      events: [event("event-3"), event("event-4")],
      hasMore: true,
      nextOffset: 4,
    },
    {
      events: [event("event-4"), event("target")],
      hasMore: false,
      nextOffset: 6,
    },
  ];

  const restored = await restoreEventsUntilTarget(
    [event("event-1"), event("event-2")],
    2,
    true,
    {
      path: "/events",
      scrollY: 100,
      detailPath: "/events/target",
      eventId: "target",
      loadedCount: 4,
    },
    async (offset, limit) => {
      calls.push({ offset, limit });
      const page = pages.shift();
      assert.ok(page);
      return page;
    }
  );

  assert.deepEqual(calls, [
    { offset: 2, limit: 2 },
    { offset: 4, limit: undefined },
  ]);
  assert.deepEqual(
    restored.current.map((ev) => ev.id),
    ["event-1", "event-2", "event-3", "event-4", "target"]
  );
  assert.equal(restored.next, 6);
  assert.equal(restored.more, false);
});
