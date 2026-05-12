import type { CampusEvent } from "@/types/event";
import { PLACEHOLDER_EVENTS } from "@/data/placeholder-events";
import { getInstagramEvents } from "@/lib/scrapers/instagram";

/**
 * Fetches events from all wired-up sources, merges, dedupes by id, sorts.
 * Each source is independent — a failure in one shouldn't kill the page.
 * Add new sources by following the instagram.ts pattern.
 */
export async function getEvents(): Promise<CampusEvent[]> {
  const results = await Promise.allSettled([getInstagramEvents()]);
  const fromSources = results.flatMap((r) =>
    r.status === "fulfilled" ? r.value : []
  );

  const merged = new Map<string, CampusEvent>();
  for (const ev of [...PLACEHOLDER_EVENTS, ...fromSources]) {
    merged.set(ev.id, ev);
  }

  return [...merged.values()].sort(
    (a, b) => new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime()
  );
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
