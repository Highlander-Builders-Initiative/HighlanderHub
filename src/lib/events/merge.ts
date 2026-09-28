import type { CampusEvent } from "@/types/event";

/** Adds the events not already loaded, keeping the feed's (sortAt, id) order. */
export function mergeUniqueEventsInFeedOrder(
  current: CampusEvent[],
  incoming: CampusEvent[]
): CampusEvent[] {
  const merged = new Map(current.map((event) => [event.id, event]));
  for (const event of incoming) {
    if (!merged.has(event.id)) merged.set(event.id, event);
  }
  return Array.from(merged.values()).sort((a, b) => {
    const byTime = Date.parse(a.sortAt) - Date.parse(b.sortAt);
    return byTime === 0 ? a.id.localeCompare(b.id) : byTime;
  });
}
