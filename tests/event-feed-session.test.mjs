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
    const scroll = await importTsModule("src/lib/scroll-restoration.ts");
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
      view: "list",
      category: "all",
      query: "",
      events,
      hasMore: true,
      nextOffset: 24,
      loadedCount: 1,
    });

    const saved = session.getSavedEventFeedSnapshot();
    assert.ok(saved);
    assert.equal(saved.path, "/events");
    assert.equal(saved.events.length, 1);
    assert.equal(saved.view, "list");

    session.saveEventFeedReturn("/events/event-1", {
      eventId: "event-1",
      eventTop: 96,
      loadedCount: 1,
    });

    const returned = scroll.getSavedScrollPosition();
    assert.ok(returned);
    assert.equal(returned.path, "/events");
    assert.equal(returned.detailPath, "/events/event-1");
    assert.equal(returned.eventId, "event-1");
    assert.equal(returned.eventTop, 96);
    assert.equal(returned.loadedCount, 1);
    assert.equal(session.getSavedEventFeedSnapshot()?.eventId, "event-1");

    globalThis.window.location.pathname = "/events/event-1";
    assert.equal(scroll.getSavedReturnPath(), "/events");
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
      view: "calendar",
      category: "social",
      query: "dance",
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
