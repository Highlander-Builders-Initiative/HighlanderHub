import type { EventCategory, CampusEvent } from "@/types/event";
import type { DayWindow } from "@/types/events-feed";
import { clearEventFeedReturnState } from "@/lib/event-feed-session";
import type { SavedScrollPosition } from "@/lib/event-feed-session";
import { fetchEventsPage, type EventsApiPage } from "@/lib/events-api";
import { mergeUniqueEventsByStart } from "@/lib/events-merge";

type EventPageFetcher = (
  offset: number,
  limit?: number
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

export async function restoreEventsUntilTarget(
  current: CampusEvent[],
  next: number,
  more: boolean,
  target: RestoreTarget,
  fetchPage: EventPageFetcher = fetchEventsPage
) {
  let restored = current;
  let restoredNext = next;
  let restoredMore = more;

  if (typeof target.loadedCount === "number") {
    const limitToFetch = Math.max(0, target.loadedCount - current.length);
    if (limitToFetch > 0) {
      const page = await fetchPage(next, limitToFetch);
      const nextEvents = mergeUniqueEventsByStart(restored, page.events);
      if (nextEvents.length === restored.length && page.nextOffset === restoredNext) {
        return { current: restored, next: restoredNext, more: restoredMore };
      }
      restored = nextEvents;
      restoredNext = page.nextOffset;
      restoredMore = page.hasMore;
    }
  }

  while (
    restoredMore &&
    !restored.some((event) => event.id === target.eventId)
  ) {
    const page = await fetchPage(restoredNext);
    const nextEvents = mergeUniqueEventsByStart(restored, page.events);
    if (nextEvents.length === restored.length && page.nextOffset === restoredNext) break;
    restored = nextEvents;
    restoredNext = page.nextOffset;
    restoredMore = page.hasMore;
  }

  return { current: restored, next: restoredNext, more: restoredMore };
}

type RestoreIntent =
  | {
      kind: "card";
      eventId: string;
      eventTop?: number;
      loadedCount?: number;
      events: CampusEvent[];
      hasMore: boolean;
      nextOffset: number;
    }
  | { kind: "scrollY"; scrollY: number }
  | { kind: "none" };

function deriveRestoreIntent(
  snapshot: RestoreSavedEventFeedSpotArgs["snapshot"],
  returnScroll: SavedScrollPosition | null,
  currentEvents: CampusEvent[],
  currentHasMore: boolean,
  currentNextOffset: number
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
      nextOffset: snapshot.nextOffset,
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
      nextOffset: snapshot?.nextOffset ?? currentNextOffset,
    };
  }

  if (returnScroll) {
    return { kind: "scrollY", scrollY: returnScroll.scrollY };
  }

  return { kind: "none" };
}

type RestoreSavedEventFeedSpotArgs = {
  snapshot: {
    path: string;
    events: CampusEvent[];
    hasMore: boolean;
    nextOffset: number;
    loadedCount: number;
    category: EventCategory | "all";
    query: string;
    dayWindow: DayWindow;
    eventId?: string;
    eventTop?: number;
  } | null;
  returnScroll: SavedScrollPosition | null;
  path: string;
  currentEvents: CampusEvent[];
  currentHasMore: boolean;
  currentNextOffset: number;
  setCategory: (next: EventCategory | "all") => void;
  setQuery: (next: string) => void;
  setDayWindow: (next: DayWindow) => void;
  setLoadedEvents: (next: CampusEvent[]) => void;
  setHasMore: (next: boolean) => void;
  setNextOffset: (next: number) => void;
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
  currentNextOffset,
  setCategory,
  setQuery,
  setDayWindow,
  setLoadedEvents,
  setHasMore,
  setNextOffset,
}: RestoreSavedEventFeedSpotArgs): Promise<boolean> {
  if (snapshot && snapshot.path !== path) return false;
  if (!snapshot && returnScroll?.path !== path) return false;

  const root = document.documentElement;
  const previousScrollBehavior = root.style.scrollBehavior;
  root.style.scrollBehavior = "auto";

  try {
    if (snapshot) {
      setCategory(snapshot.category);
      setQuery(snapshot.query);
      setDayWindow(snapshot.dayWindow);
      setLoadedEvents(snapshot.events);
      setHasMore(snapshot.hasMore);
      setNextOffset(snapshot.nextOffset);
    }

    await settleFrame();

    const intent = deriveRestoreIntent(
      snapshot,
      returnScroll,
      currentEvents,
      currentHasMore,
      currentNextOffset
    );
    if (intent.kind === "none") return false;

    if (intent.kind === "scrollY") {
      const rootScroller = document.scrollingElement ?? document.documentElement;
      rootScroller.scrollTop = intent.scrollY;
      clearEventFeedReturnState();
      return true;
    }

    const restored = await restoreEventsUntilTarget(
      intent.events,
      intent.nextOffset,
      intent.hasMore,
      intent
    );

    setLoadedEvents(restored.current);
    setHasMore(restored.more);
    setNextOffset(restored.next);

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
