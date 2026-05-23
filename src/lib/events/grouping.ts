import type { CampusEvent } from "@/types/event";
import { pacificDayKey } from "@/lib/dates";

/**
 * Returns events grouped by Pacific-local day (YYYY-MM-DD). Pacific, not UTC:
 * an 8pm Pacific event has a UTC timestamp on the following calendar day, so
 * a naive slice of the ISO string buckets it under tomorrow.
 */
export function groupByDay(events: CampusEvent[]): Map<string, CampusEvent[]> {
  const map = new Map<string, CampusEvent[]>();
  for (const ev of events) {
    const key = pacificDayKey(ev.startsAt);
    const bucket = map.get(key);
    if (bucket) bucket.push(ev);
    else map.set(key, [ev]);
  }
  return map;
}
