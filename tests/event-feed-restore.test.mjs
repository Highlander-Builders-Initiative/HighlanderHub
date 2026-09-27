import assert from "node:assert/strict";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

function event(id) {
  return { id };
}

const ALL_FILTERS = { category: "all", query: "", dayWindow: "all" };

// A feed resumes after its last loaded event.
const after = (id, startsAt = "2026-05-20T18:30:00.000-07:00") => ({ startsAt, id });

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
    "src/lib/events/feed-restore.ts"
  );
  const calls = [];
  const pages = [
    {
      events: [event("event-3"), event("event-4")],
      hasMore: true,
      cursor: after("event-4"),
    },
    {
      events: [event("event-4"), event("target")],
      hasMore: false,
      cursor: after("target"),
    },
  ];

  const restored = await restoreEventsUntilTarget(
    [event("event-1"), event("event-2")],
    after("event-2"),
    true,
    { eventId: "target", loadedCount: 4 },
    ALL_FILTERS,
    async (cursor, limit, filters) => {
      calls.push({ cursor, limit, filters });
      const page = pages.shift();
      assert.ok(page);
      return page;
    }
  );

  assert.deepEqual(calls, [
    { cursor: after("event-2"), limit: 2, filters: ALL_FILTERS },
    { cursor: after("event-4"), limit: undefined, filters: ALL_FILTERS },
  ]);
  assert.deepEqual(
    restored.current.map((ev) => ev.id),
    ["event-1", "event-2", "event-3", "event-4", "target"]
  );
  assert.deepEqual(restored.next, after("target"));
  assert.equal(restored.more, false);
});

test("restoreSavedEventFeedSpot handles card and scroll restores from a derived intent", async () => {
  const session = await importTsModule("src/lib/events/feed-session.ts");
  const restore = await importTsModule("src/lib/events/feed-restore.ts");
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
      cursor: after("event-1"),
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
          cursor: after("target", "2026-05-20T20:30:00.000-07:00"),
        }),
      };
    };

    const didRestore = await restore.restoreSavedEventFeedSpot({
      snapshot: session.getSavedEventFeedSnapshot(),
      returnScroll: session.getSavedScrollPosition(),
      path: "/events",
      currentEvents: events,
      currentHasMore: true,
      currentCursor: after("event-1"),
      pageFilters: ALL_FILTERS,
      applyRestore(patch) {
        if (patch.loadedEvents !== undefined) {
          root.events = patch.loadedEvents;
        }
        if (patch.hasMore !== undefined) {
          root.hasMore = patch.hasMore;
        }
        if (patch.cursor !== undefined) {
          root.cursor = patch.cursor;
        }
      },
    });

    assert.equal(didRestore, true);
    assert.equal(root.scrollTop, 156);
    assert.equal(calls.length, 1);
    assert.match(calls[0], /afterId=event-1/);
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
      cursor: null,
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
      currentCursor: null,
      pageFilters: ALL_FILTERS,
      applyRestore() {},
    });

    assert.equal(scrollDidRestore, true);
    assert.equal(root.scrollTop, 333);
  } finally {
    harness.restore();
  }
});

test("restoreSavedEventFeedSpot uses snapshot pagination when return scroll has eventId but snapshot does not", async () => {
  const session = await importTsModule("src/lib/events/feed-session.ts");
  const restore = await importTsModule("src/lib/events/feed-restore.ts");
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
      cursor: after("event-2", "2026-05-20T19:30:00.000-07:00"),
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
          cursor: after("target", "2026-05-20T20:30:00.000-07:00"),
        }),
      };
    };

    const didRestore = await restore.restoreSavedEventFeedSpot({
      snapshot: session.getSavedEventFeedSnapshot(),
      returnScroll: session.getSavedScrollPosition(),
      path: "/events",
      currentEvents: staleMountEvents,
      currentHasMore: false,
      currentCursor: after("stale-only", "2026-05-19T12:00:00.000-07:00"),
      pageFilters: ALL_FILTERS,
      applyRestore(patch) {
        if (patch.loadedEvents !== undefined) {
          root.events = patch.loadedEvents;
        }
      },
    });

    assert.equal(didRestore, true);
    assert.equal(calls.length, 1);
    assert.match(calls[0], /afterId=event-2/);
    assert.doesNotMatch(calls[0], /afterId=stale-only/);
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

test("restoreSavedEventFeedSpot pages with the snapshot filters that own the cursor", async () => {
  const session = await importTsModule("src/lib/events/feed-session.ts");
  const restore = await importTsModule("src/lib/events/feed-restore.ts");
  const harness = installRestoreDomHarness({ cardTop: 40 });
  const { root } = harness;

  try {
    const events = [
      richEvent("event-1", "2026-05-20T18:30:00.000-07:00"),
    ];

    session.saveEventFeedSnapshot({
      path: "/events",
      scrollY: 420,
      category: "sports",
      query: "",
      dayWindow: "all",
      events,
      hasMore: true,
      cursor: after("event-1"),
      loadedCount: 1,
    });
    session.saveEventFeedReturn("/events/target", {
      eventId: "target",
      eventTop: 24,
      loadedCount: 3,
    });

    const calls = [];
    globalThis.fetch = async (url) => {
      calls.push(String(url));
      return {
        ok: true,
        json: async () => ({
          events: [richEvent("target", "2026-05-20T20:30:00.000-07:00")],
          hasMore: false,
          cursor: after("target", "2026-05-20T20:30:00.000-07:00"),
        }),
      };
    };

    const didRestore = await restore.restoreSavedEventFeedSpot({
      snapshot: session.getSavedEventFeedSnapshot(),
      returnScroll: session.getSavedScrollPosition(),
      path: "/events",
      currentEvents: events,
      currentHasMore: true,
      currentCursor: after("event-1"),
      pageFilters: ALL_FILTERS,
      applyRestore(patch) {
        if (patch.loadedEvents !== undefined) {
          root.events = patch.loadedEvents;
        }
      },
    });

    assert.equal(didRestore, true);
    assert.equal(calls.length, 1);
    assert.match(calls[0], /afterId=event-1/);
    assert.match(calls[0], /cat=sports/);
    assert.doesNotMatch(calls[0], /q=/);
  } finally {
    harness.restore();
  }
});
