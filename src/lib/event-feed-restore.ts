import type { EventCategory, CampusEvent } from "@/types/event";
import type { DayWindow } from "@/types/events-feed";
import { clearEventFeedReturnState } from "@/lib/event-feed-session";
import type { SavedScrollPosition } from "@/lib/scroll-restoration";

type EventsApiPage = {
  events: CampusEvent[];
  hasMore: boolean;
  nextOffset: number;
};

type EventPageFetcher = (
  offset: number,
  limit?: number
) => Promise<EventsApiPage>;

async function fetchEventsPage(offset: number, limit?: number) {
  const params = new URLSearchParams({ offset: String(offset) });
  if (typeof limit === "number") {
    params.set("limit", String(limit));
  }

  const response = await fetch(`/api/events?${params}`);
  if (!response.ok) throw new Error("Unable to load more events.");
  return (await response.json()) as EventsApiPage;
}

function appendUniqueEvents(current: CampusEvent[], incoming: CampusEvent[]) {
  const seen = new Set(current.map((event) => event.id));
  return incoming.filter((event) => !seen.has(event.id));
}

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
  returnScroll: SavedScrollPosition,
  fetchPage: EventPageFetcher = fetchEventsPage
) {
  let restored = current;
  let restoredNext = next;
  let restoredMore = more;

  if (typeof returnScroll.loadedCount === "number") {
    const limitToFetch = Math.max(0, returnScroll.loadedCount - current.length);
    if (limitToFetch > 0) {
      const page = await fetchPage(next, limitToFetch);
      const nextEvents = appendUniqueEvents(restored, page.events);
      if (nextEvents.length === 0 && page.nextOffset === restoredNext) {
        return { current: restored, next: restoredNext, more: restoredMore };
      }
      restored = [...restored, ...nextEvents];
      restoredNext = page.nextOffset;
      restoredMore = page.hasMore;
    }
  }

  while (
    restoredMore &&
    !restored.some((event) => event.id === returnScroll.eventId)
  ) {
    const page = await fetchPage(restoredNext);
    const nextEvents = appendUniqueEvents(restored, page.events);
    if (nextEvents.length === 0 && page.nextOffset === restoredNext) break;
    restored = [...restored, ...nextEvents];
    restoredNext = page.nextOffset;
    restoredMore = page.hasMore;
  }

  return { current: restored, next: restoredNext, more: restoredMore };
}

type RestoreSavedEventFeedSpotArgs = {
  snapshot: {
    path: string;
    events: CampusEvent[];
    hasMore: boolean;
    nextOffset: number;
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

    if (snapshot?.eventId && returnScroll?.eventId === snapshot.eventId) {
      const restored = await restoreEventsUntilTarget(
        snapshot.events,
        snapshot.nextOffset,
        snapshot.hasMore,
        returnScroll
      );

      setLoadedEvents(restored.current);
      setHasMore(restored.more);
      setNextOffset(restored.next);

      await settleFrame();

      if (restoreToEventCard(returnScroll.eventId, returnScroll.eventTop)) {
        clearEventFeedReturnState();
        return true;
      }
    } else if (snapshot?.eventId) {
      if (restoreToEventCard(snapshot.eventId, snapshot.eventTop)) {
        clearEventFeedReturnState();
        return true;
      }
    } else if (returnScroll?.eventId) {
      const restored = await restoreEventsUntilTarget(
        currentEvents,
        currentNextOffset,
        currentHasMore,
        returnScroll
      );

      setLoadedEvents(restored.current);
      setHasMore(restored.more);
      setNextOffset(restored.next);

      await settleFrame();

      if (restoreToEventCard(returnScroll.eventId, returnScroll.eventTop)) {
        clearEventFeedReturnState();
        return true;
      }
    } else if (returnScroll) {
      const rootScroller = document.scrollingElement ?? document.documentElement;
      rootScroller.scrollTop = returnScroll.scrollY;
      clearEventFeedReturnState();
      return true;
    }
    return false;
  } finally {
    root.style.scrollBehavior = previousScrollBehavior;
  }
}
