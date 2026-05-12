import type { CampusEvent } from "@/types/event";

/**
 * Returns events grouped by day (YYYY-MM-DD).
 */
export function groupByDay(events: CampusEvent[]): Map<string, CampusEvent[]> {
  const map = new Map<string, CampusEvent[]>();
  for (const ev of events) {
    const key = ev.startsAt.slice(0, 10);
    const bucket = map.get(key);
    if (bucket) bucket.push(ev);
    else map.set(key, [ev]);
  }
  return map;
}
