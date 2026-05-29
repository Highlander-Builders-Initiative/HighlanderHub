import type { CampusEvent } from "@/types/event";

export type EventsApiPage = {
  events: CampusEvent[];
  hasMore: boolean;
  nextOffset: number;
};

export async function fetchEventsPage(
  offset: number,
  limit?: number
): Promise<EventsApiPage> {
  const params = new URLSearchParams({ offset: String(offset) });
  if (typeof limit === "number") {
    params.set("limit", String(limit));
  }

  const response = await fetch(`/api/events?${params}`);
  if (!response.ok) throw new Error("Unable to load more events.");
  return (await response.json()) as EventsApiPage;
}

export async function fetchEventsByIds(
  ids: string[]
): Promise<CampusEvent[]> {
  if (ids.length === 0) return [];

  const params = new URLSearchParams({ ids: ids.join(",") });
  const response = await fetch(`/api/events?${params}`);
  if (!response.ok) throw new Error("Unable to load search results.");
  const payload = (await response.json()) as { events: CampusEvent[] };
  return payload.events;
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
