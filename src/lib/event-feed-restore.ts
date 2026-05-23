import type { CampusEvent } from "@/types/event";
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
