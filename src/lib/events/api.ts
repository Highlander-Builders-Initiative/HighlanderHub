import type { CampusEvent } from "@/types/event";
import type {
  CategoryValue,
  DayWindow,
} from "@/components/events/events-filters";

export type EventsApiPage = {
  events: CampusEvent[];
  hasMore: boolean;
  nextOffset: number;
};

export async function fetchEventsPage(
  offset: number,
  limit?: number,
  filters?: {
    query: string;
    category: CategoryValue;
    dayWindow: DayWindow;
  }
): Promise<EventsApiPage> {
  const params = new URLSearchParams({ offset: String(offset) });
  if (typeof limit === "number") {
    params.set("limit", String(limit));
  }
  if (filters) {
    if (filters.query.trim()) params.set("q", filters.query.trim());
    if (filters.category !== "all") params.set("cat", filters.category);
    if (filters.dayWindow !== "all") params.set("when", filters.dayWindow);
  }

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
