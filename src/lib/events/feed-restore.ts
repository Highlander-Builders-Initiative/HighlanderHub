import type { EventCategory, CampusEvent } from "@/types/event";
import type { DayWindow, EventFeedCursor } from "@/types/events-feed";
import type { EventFeedQuery } from "@/components/events/events-filters";
import {
  clearEventFeedReturnState,
  type SavedEventFeedSnapshot,
  type SavedScrollPosition,
} from "@/lib/events/feed-session";
import { fetchEventsPage, type EventsApiPage } from "@/lib/events/api";
import { mergeUniqueEventsByStart } from "@/lib/events/merge";

export type EventFeedRestorePatch = {
  category?: EventCategory | "all";
  query?: string;
  dayWindow?: DayWindow;
  loadedEvents?: CampusEvent[];
  hasMore?: boolean;
  cursor?: EventFeedCursor | null;
};

type EventPageFetcher = (
  after: EventFeedCursor | null,
  limit: number | undefined,
  filters: EventFeedQuery
) => Promise<EventsApiPage>;

type RestoreTarget = {
  eventId: string;
  loadedCount?: number;
};

export function restoreToEventCard(eventId: string, eventTop = 0) {
  const target = document.querySelector<HTMLElement>(
    `[data-event-id="${CSS.escape(eventId)}"]`
  );
  if (!target) return false;

  const root = document.scrollingElement ?? document.documentElement;
  root.scrollTop = window.scrollY + target.getBoundingClientRect().top - eventTop;
  return true;
}

function sameCursor(a: EventFeedCursor | null, b: EventFeedCursor | null) {
  return a?.startsAt === b?.startsAt && a?.id === b?.id;
}

export async function restoreEventsUntilTarget(
  current: CampusEvent[],
  next: EventFeedCursor | null,
  more: boolean,
  target: RestoreTarget,
  filters: EventFeedQuery,
  fetchPage: EventPageFetcher = fetchEventsPage
) {
  let restored = current;
  let restoredNext = next;
  let restoredMore = more;

  if (typeof target.loadedCount === "number") {
    const limitToFetch = Math.max(0, target.loadedCount - current.length);
    if (limitToFetch > 0) {
      const page = await fetchPage(next, limitToFetch, filters);
      const nextEvents = mergeUniqueEventsByStart(restored, page.events);
      if (nextEvents.length === restored.length && sameCursor(page.cursor, restoredNext)) {
        return { current: restored, next: restoredNext, more: restoredMore };
      }
      restored = nextEvents;
      restoredNext = page.cursor;
      restoredMore = page.hasMore;
    }
  }

  while (
    restoredMore &&
    !restored.some((event) => event.id === target.eventId)
  ) {
    const page = await fetchPage(restoredNext, undefined, filters);
    const nextEvents = mergeUniqueEventsByStart(restored, page.events);
    if (nextEvents.length === restored.length && sameCursor(page.cursor, restoredNext)) break;
    restored = nextEvents;
    restoredNext = page.cursor;
    restoredMore = page.hasMore;
  }

  return { current: restored, next: restoredNext, more: restoredMore };
}

export type RestoreIntent =
  | {
      kind: "card";
      eventId: string;
      eventTop?: number;
      loadedCount?: number;
      events: CampusEvent[];
      hasMore: boolean;
      cursor: EventFeedCursor | null;
    }
  | { kind: "scrollY"; scrollY: number }
  | { kind: "none" };

export function deriveRestoreIntent(
  snapshot: RestoreSnapshot | null,
  returnScroll: SavedScrollPosition | null,
  currentEvents: CampusEvent[],
  currentHasMore: boolean,
  currentCursor: EventFeedCursor | null
): RestoreIntent {
  if (snapshot?.eventId) {
    const matchingReturnTarget =
      returnScroll?.eventId === snapshot.eventId ? returnScroll : null;

    return {
      kind: "card",
      eventId: snapshot.eventId,
      eventTop: matchingReturnTarget
        ? matchingReturnTarget.eventTop
        : snapshot.eventTop,
      loadedCount: matchingReturnTarget?.loadedCount ?? snapshot.loadedCount,
      events: snapshot.events,
      hasMore: snapshot.hasMore,
      cursor: snapshot.cursor,
    };
  }

  if (returnScroll?.eventId) {
    return {
      kind: "card",
      eventId: returnScroll.eventId,
      eventTop: returnScroll.eventTop,
      loadedCount: returnScroll.loadedCount,
      events: snapshot?.events ?? currentEvents,
      hasMore: snapshot?.hasMore ?? currentHasMore,
      cursor: snapshot ? snapshot.cursor : currentCursor,
    };
  }

  if (returnScroll) {
    return { kind: "scrollY", scrollY: returnScroll.scrollY };
  }

  return { kind: "none" };
}

export type RestoreSnapshot = Omit<SavedEventFeedSnapshot, "savedAt" | "scrollY">;

type RestoreSavedEventFeedSpotArgs = {
  snapshot: RestoreSnapshot | null;
  returnScroll: SavedScrollPosition | null;
  path: string;
  currentEvents: CampusEvent[];
  currentHasMore: boolean;
  currentCursor: EventFeedCursor | null;
  pageFilters: EventFeedQuery;
  applyRestore: (patch: EventFeedRestorePatch) => void;
};

async function settleFrame() {
  await new Promise((resolve) => requestAnimationFrame(resolve));
}

export async function restoreSavedEventFeedSpot({
  snapshot,
  returnScroll,
  path,
  currentEvents,
  currentHasMore,
  currentCursor,
  pageFilters,
  applyRestore,
}: RestoreSavedEventFeedSpotArgs): Promise<boolean> {
  if (snapshot && snapshot.path !== path) return false;
  if (!snapshot && returnScroll?.path !== path) return false;

  const root = document.documentElement;
  const previousScrollBehavior = root.style.scrollBehavior;
  root.style.scrollBehavior = "auto";

  try {
    if (snapshot) {
      applyRestore({
        category: snapshot.category,
        query: snapshot.query,
        dayWindow: snapshot.dayWindow,
        loadedEvents: snapshot.events,
        hasMore: snapshot.hasMore,
        cursor: snapshot.cursor,
      });
    }

    await settleFrame();

    const intent = deriveRestoreIntent(
      snapshot,
      returnScroll,
      currentEvents,
      currentHasMore,
      currentCursor
    );
    if (intent.kind === "none") return false;

    if (intent.kind === "scrollY") {
      const rootScroller = document.scrollingElement ?? document.documentElement;
      rootScroller.scrollTop = intent.scrollY;
      clearEventFeedReturnState();
      return true;
    }

    const listFilters: EventFeedQuery = snapshot
      ? {
          category: snapshot.category,
          query: snapshot.query,
          dayWindow: snapshot.dayWindow,
        }
      : pageFilters;

    const restored = await restoreEventsUntilTarget(
      intent.events,
      intent.cursor,
      intent.hasMore,
      intent,
      listFilters
    );

    applyRestore({
      loadedEvents: restored.current,
      hasMore: restored.more,
      cursor: restored.next,
    });

    await settleFrame();

    if (restoreToEventCard(intent.eventId, intent.eventTop)) {
      clearEventFeedReturnState();
      return true;
    }
    return false;
  } finally {
    root.style.scrollBehavior = previousScrollBehavior;
  }
}
