import type { CampusEvent } from "@/types/event";
import type { EventFeedCursor } from "@/types/events-feed";
import type { EventFeedQuery } from "@/components/events/events-filters";
import { CALENDAR_GRID_DAYS, addPacificDays } from "@/lib/dates";

export type EventsApiPage = {
  events: CampusEvent[];
  hasMore: boolean;
  cursor: EventFeedCursor | null;
};

export async function fetchEventsPage(
  after: EventFeedCursor | null,
  limit: number | undefined,
  filters: EventFeedQuery
): Promise<EventsApiPage> {
  const params = new URLSearchParams();
  if (after) {
    params.set("after", after.startsAt);
    params.set("afterId", after.id);
  }
  if (typeof limit === "number") {
    params.set("limit", String(limit));
  }
  if (filters.query.trim()) params.set("q", filters.query.trim());
  if (filters.category !== "all") params.set("cat", filters.category);
  if (filters.dayWindow !== "all") params.set("when", filters.dayWindow);

  const response = await fetch(`/api/events?${params}`);
  if (!response.ok) throw new Error("Unable to load more events.");
  return (await response.json()) as EventsApiPage;
}

export async function fetchCalendarEvents(
  startDayKey: string,
  endDayKey: string
): Promise<CampusEvent[]> {
  const params = new URLSearchParams({
    start: startDayKey,
    end: endDayKey,
  });

  const response = await fetch(`/api/events/calendar?${params}`);
  if (!response.ok) throw new Error("Unable to load calendar events.");
  const payload = (await response.json()) as { events: CampusEvent[] };
  return payload.events;
}

/** Any range of days, one grid per request (the calendar route's limit). */
export async function fetchCalendarRange(
  startDayKey: string,
  endDayKey: string
): Promise<CampusEvent[]> {
  const requests: Promise<CampusEvent[]>[] = [];
  for (
    let from = startDayKey;
    from <= endDayKey;
    from = addPacificDays(from, CALENDAR_GRID_DAYS)
  ) {
    const to = addPacificDays(from, CALENDAR_GRID_DAYS - 1);
    requests.push(fetchCalendarEvents(from, to < endDayKey ? to : endDayKey));
  }
  return (await Promise.all(requests)).flat();
}
