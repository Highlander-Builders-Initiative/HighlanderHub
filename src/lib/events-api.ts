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
