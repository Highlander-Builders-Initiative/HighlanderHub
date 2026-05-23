import assert from "node:assert/strict";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

function event(id) {
  return { id };
}

function richEvent(id, startsAt) {
  return {
    id,
    title: id,
    description: id,
    startsAt,
    location: "HUB",
    host: "QA",
    category: "social",
    tags: [],
    source: "manual",
    isFree: true,
    rsvpRequired: false,
    scrapedAt: "2026-05-18T12:00:00.000Z",
  };
}

function makeSessionStorage() {
  const store = new Map();

  return {
    store,
    setItem(key, value) {
      store.set(key, String(value));
    },
    getItem(key) {
      return store.has(key) ? store.get(key) : null;
    },
    removeItem(key) {
      store.delete(key);
    },
  };
}

function installRestoreDomHarness({ cardTop } = {}) {
  const sessionStorage = makeSessionStorage();
  const root = { scrollTop: 0 };
  const previousWindow = globalThis.window;
  const previousDocument = globalThis.document;
  const previousFetch = globalThis.fetch;
  const previousRaf = globalThis.requestAnimationFrame;
  const previousCSS = globalThis.CSS;
  const requestAnimationFrame = (cb) => {
    cb();
    return 0;
  };

  globalThis.window = {
    location: { pathname: "/events", search: "" },
    sessionStorage,
    scrollY: 120,
    document: { scrollingElement: root, documentElement: root },
    requestAnimationFrame,
  };
  globalThis.document = {
    scrollingElement: root,
    documentElement: { ...root, style: {} },
    querySelector(selector) {
      if (selector.includes("target")) {
        return {
          getBoundingClientRect() {
            return { top: cardTop };
          },
        };
      }
      return null;
    },
  };
  globalThis.CSS = {
    escape(value) {
      return String(value);
    },
  };
  globalThis.requestAnimationFrame = requestAnimationFrame;

  return {
    root,
    sessionStorage,
    restore() {
      globalThis.window = previousWindow;
      globalThis.document = previousDocument;
      globalThis.fetch = previousFetch;
      globalThis.requestAnimationFrame = previousRaf;
      globalThis.CSS = previousCSS;
    },
  };
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
    { eventId: "target", loadedCount: 4 },
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

test("restoreSavedEventFeedSpot handles card and scroll restores from a derived intent", async () => {
  const session = await importTsModule("src/lib/event-feed-session.ts");
  const restore = await importTsModule("src/lib/event-feed-restore.ts");
  const harness = installRestoreDomHarness({ cardTop: 60 });
  const { root } = harness;

  try {
    const events = [
      richEvent("event-1", "2026-05-20T18:30:00.000-07:00"),
    ];

    session.saveEventFeedSnapshot({
      path: "/events",
      scrollY: 420,
      category: "all",
      query: "",
      dayWindow: "all",
      events,
      hasMore: true,
      nextOffset: 24,
      loadedCount: 1,
    });
    session.saveEventFeedReturn("/events/target", {
      eventId: "target",
      eventTop: 24,
      loadedCount: 3,
    });

    const calls = [];
    globalThis.fetch = async (url) => {
      calls.push(url);
      return {
        ok: true,
        json: async () => ({
          events: [
            richEvent("event-2", "2026-05-20T19:30:00.000-07:00"),
            richEvent("target", "2026-05-20T20:30:00.000-07:00"),
          ],
          hasMore: false,
          nextOffset: 26,
        }),
      };
    };

    const didRestore = await restore.restoreSavedEventFeedSpot({
      snapshot: session.getSavedEventFeedSnapshot(),
      returnScroll: session.getSavedScrollPosition(),
      path: "/events",
      currentEvents: events,
      currentHasMore: true,
      currentNextOffset: 24,
      setCategory() {},
      setQuery() {},
      setDayWindow() {},
      setLoadedEvents(next) {
        root.events = next;
      },
      setHasMore(next) {
        root.hasMore = next;
      },
      setNextOffset(next) {
        root.nextOffset = next;
      },
    });

    assert.equal(didRestore, true);
    assert.equal(root.scrollTop, 156);
    assert.equal(calls.length, 1);
    assert.match(calls[0], /offset=24/);
    assert.match(calls[0], /limit=2/);
    assert.deepEqual(
      root.events.map((ev) => ev.id),
      ["event-1", "event-2", "target"]
    );

    session.saveEventFeedReturn("/events/target", {});
    root.scrollTop = 0;
    session.saveEventFeedSnapshot({
      path: "/events",
      scrollY: 420,
      category: "all",
      query: "",
      dayWindow: "all",
      events: [],
      hasMore: false,
      nextOffset: 0,
      loadedCount: 0,
    });

    const scrollDidRestore = await restore.restoreSavedEventFeedSpot({
      snapshot: null,
      returnScroll: {
        path: "/events",
        scrollY: 333,
        detailPath: "/events/target",
      },
      path: "/events",
      currentEvents: [],
      currentHasMore: false,
      currentNextOffset: 0,
      setCategory() {},
      setQuery() {},
      setDayWindow() {},
      setLoadedEvents() {},
      setHasMore() {},
      setNextOffset() {},
    });

    assert.equal(scrollDidRestore, true);
    assert.equal(root.scrollTop, 333);
  } finally {
    harness.restore();
  }
});

test("restoreSavedEventFeedSpot uses snapshot pagination when return scroll has eventId but snapshot does not", async () => {
  const session = await importTsModule("src/lib/event-feed-session.ts");
  const restore = await importTsModule("src/lib/event-feed-restore.ts");
  const harness = installRestoreDomHarness({ cardTop: 40 });
  const { root, sessionStorage } = harness;

  try {
    const snapshotEvents = [
      richEvent("event-1", "2026-05-20T18:30:00.000-07:00"),
      richEvent("event-2", "2026-05-20T19:30:00.000-07:00"),
    ];
    const staleMountEvents = [richEvent("stale-only", "2026-05-19T12:00:00.000-07:00")];

    session.saveEventFeedSnapshot({
      path: "/events",
      scrollY: 420,
      category: "all",
      query: "",
      dayWindow: "all",
      events: snapshotEvents,
      hasMore: true,
      nextOffset: 24,
      loadedCount: 2,
    });
    sessionStorage.setItem(
      "highlanderhub.returnScroll",
      JSON.stringify({
        path: "/events",
        scrollY: 420,
        detailPath: "/events/target",
        eventId: "target",
        eventTop: 20,
        loadedCount: 2,
      })
    );

    const calls = [];
    globalThis.fetch = async (url) => {
      calls.push(url);
      return {
        ok: true,
        json: async () => ({
          events: [richEvent("target", "2026-05-20T20:30:00.000-07:00")],
          hasMore: false,
          nextOffset: 26,
        }),
      };
    };

    const didRestore = await restore.restoreSavedEventFeedSpot({
      snapshot: session.getSavedEventFeedSnapshot(),
      returnScroll: session.getSavedScrollPosition(),
      path: "/events",
      currentEvents: staleMountEvents,
      currentHasMore: false,
      currentNextOffset: 0,
      setCategory() {},
      setQuery() {},
      setDayWindow() {},
      setLoadedEvents(next) {
        root.events = next;
      },
      setHasMore() {},
      setNextOffset() {},
    });

    assert.equal(didRestore, true);
    assert.equal(calls.length, 1);
    assert.match(calls[0], /offset=24/);
    assert.doesNotMatch(calls[0], /offset=0/);
    assert.deepEqual(
      root.events.map((ev) => ev.id),
      ["event-1", "event-2", "target"]
    );
    assert.doesNotMatch(
      root.events.map((ev) => ev.id).join(","),
      /stale-only/
    );
  } finally {
    harness.restore();
  }
});
