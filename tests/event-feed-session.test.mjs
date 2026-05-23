import assert from "node:assert/strict";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

function makeSessionStorage(store) {
  return {
    getItem(key) {
      return store.has(key) ? store.get(key) : null;
    },
    setItem(key, value) {
      store.set(key, String(value));
    },
    removeItem(key) {
      store.delete(key);
    },
  };
}

function installBrowserEnv({
  pathname = "/events",
  search = "",
  scrollY = 420,
} = {}) {
  const store = new Map();
  const sessionStorage = makeSessionStorage(store);
  const document = {
    documentElement: { scrollTop: 0 },
    scrollingElement: { scrollTop: 0 },
  };
  const window = {
    location: { pathname, search },
    sessionStorage,
    scrollY,
    document,
  };

  const previousWindow = globalThis.window;
  const previousDocument = globalThis.document;

  globalThis.window = window;
  globalThis.document = document;

  return {
    store,
    restore() {
      globalThis.window = previousWindow;
      globalThis.document = previousDocument;
    },
  };
}

test("event feed session keeps the list snapshot and return metadata together", async () => {
  const env = installBrowserEnv();
  const previousNow = Date.now;
  Date.now = () => 1_700_000_000_000;

  try {
    const session = await importTsModule("src/lib/event-feed-session.ts");
    const events = [
      {
        id: "event-1",
        title: "Event 1",
        description: "Desc",
        startsAt: "2026-05-20T18:30:00.000-07:00",
        location: "HUB 302",
        host: "QA",
        category: "social",
        tags: [],
        source: "manual",
        isFree: true,
        rsvpRequired: false,
        scrapedAt: "2026-05-18T12:00:00.000Z",
      },
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

    const saved = session.getSavedEventFeedSnapshot();
    assert.ok(saved);
    assert.equal(saved.path, "/events");
    assert.equal(saved.events.length, 1);

    session.saveEventFeedReturn("/events/event-1", {
      eventId: "event-1",
      eventTop: 96,
      loadedCount: 1,
    });

    const returned = session.getSavedScrollPosition();
    assert.ok(returned);
    assert.equal(returned.path, "/events");
    assert.equal(returned.detailPath, "/events/event-1");
    assert.equal(returned.eventId, "event-1");
    assert.equal(returned.eventTop, 96);
    assert.equal(returned.loadedCount, 1);
    assert.equal(session.getSavedEventFeedSnapshot()?.eventId, "event-1");

    globalThis.window.location.pathname = "/events/event-1";
    assert.equal(session.getSavedReturnPath(), "/events");
  } finally {
    Date.now = previousNow;
    env.restore();
  }
});

test("event feed session ignores stale snapshots on a fresh events visit", async () => {
  const env = installBrowserEnv();
  const previousNow = Date.now;
  Date.now = () => 1_700_000_000_000;

  try {
    const session = await importTsModule("src/lib/event-feed-session.ts");
    session.saveEventFeedSnapshot({
      path: "/events",
      scrollY: 900,
      category: "all",
      query: "",
      dayWindow: "weekend",
      events: [],
      hasMore: true,
      nextOffset: 24,
      loadedCount: 24,
    });

    assert.ok(session.getSavedEventFeedSnapshot());
    assert.equal(session.getSavedEventFeedSnapshotForRestore(), null);

    session.saveEventFeedReturn("/events/event-1", {
      eventId: "event-1",
      eventTop: 96,
      loadedCount: 24,
    });

    assert.ok(session.getSavedEventFeedSnapshotForRestore());
  } finally {
    Date.now = previousNow;
    env.restore();
  }
});

test("event feed session entries expire after ten minutes", async () => {
  const env = installBrowserEnv();
  const previousNow = Date.now;
  Date.now = () => 1_700_000_000_000;

  try {
    const session = await importTsModule("src/lib/event-feed-session.ts");
    session.saveEventFeedSnapshot({
      path: "/events",
      scrollY: 420,
      category: "social",
      query: "dance",
      dayWindow: "today",
      events: [],
      hasMore: false,
      nextOffset: 0,
      loadedCount: 0,
    });

    Date.now = () => 1_700_000_000_000 + 10 * 60 * 1000 + 1;

    assert.equal(session.getSavedEventFeedSnapshot(), null);
    assert.equal(env.store.size, 0);
  } finally {
    Date.now = previousNow;
    env.restore();
  }
});

test("event feed session rejects stale calendar snapshots as invalid", async () => {
  const env = installBrowserEnv();

  try {
    const session = await importTsModule("src/lib/event-feed-session.ts");
    env.store.set(
      "highlanderhub.eventFeed",
      JSON.stringify({
        path: "/events",
        scrollY: 420,
        events: [],
        hasMore: false,
        nextOffset: 0,
        view: "calendar",
        category: "all",
        query: "",
        dayWindow: "all",
        loadedCount: 0,
        savedAt: 1_700_000_000_000,
      })
    );

    assert.equal(session.getSavedEventFeedSnapshot(), null);
  } finally {
    env.restore();
  }
});

test("event feed session accepts every generated category value", async () => {
  const env = installBrowserEnv({ search: "?category=club" });
  const previousNow = Date.now;
  Date.now = () => 1_700_000_000_000;

  try {
    const session = await importTsModule("src/lib/event-feed-session.ts");
    const { EVENT_CATEGORIES } = await importTsModule("src/types/event.ts");

    for (const category of EVENT_CATEGORIES) {
      const search = `?category=${category}`;
      const path = `/events${search}`;
      globalThis.window.location.search = search;
      env.store.set(
        "highlanderhub.eventFeed",
        JSON.stringify({
          path,
          scrollY: 420,
          events: [],
          hasMore: false,
          nextOffset: 0,
          category,
          query: "",
          dayWindow: "all",
          loadedCount: 0,
          savedAt: 1_700_000_000_000,
        })
      );

      const saved = session.getSavedEventFeedSnapshot();
      assert.ok(saved, `expected ${category} snapshot to be accepted`);
      assert.equal(saved.category, category);
    }
  } finally {
    Date.now = previousNow;
    env.restore();
  }
});
