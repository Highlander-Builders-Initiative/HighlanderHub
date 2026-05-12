import type { CampusEvent } from "@/types/event";
import { PLACEHOLDER_EVENTS } from "@/data/placeholder-events";

/**
 * Fetches events from the data source.
 *
 * RIGHT NOW: returns placeholder data from src/data/placeholder-events.ts
 *
 * LATER: replace this with calls to:
 *   - /api/events  (Next.js route that reads from a DB or cache populated by scrapers)
 *   - Direct DB query (if using Postgres/Supabase/etc. and this runs server-side)
 *
 * The contract: it returns CampusEvent[] sorted by startsAt ascending.
 * As long as scraper output conforms to the CampusEvent type, the UI
 * doesn't need to change.
 */
export async function getEvents(): Promise<CampusEvent[]> {
  // TODO: swap for real fetch once scraper + API are up
  // const res = await fetch("/api/events", { cache: "no-store" });
  // const data = await res.json();
  // return data.events;

  const sorted = [...PLACEHOLDER_EVENTS].sort(
    (a, b) => new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime()
  );
  return sorted;
}

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
