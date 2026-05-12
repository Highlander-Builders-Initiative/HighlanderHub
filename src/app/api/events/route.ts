import { NextResponse } from "next/server";
import { getEvents } from "@/lib/events";

/**
 * GET /api/events
 *
 * Returns the current list of events as JSON.
 *
 * RIGHT NOW: just returns placeholder data via getEvents().
 *
 * LATER: this route should read from whatever data store the scrapers
 * populate (Postgres, Supabase, a JSON file in /tmp, etc.). The scrapers
 * themselves should be separate processes — either cron jobs that write
 * to the store, or invoked from a separate /api/scrape route.
 *
 * Suggested scraper architecture:
 *   - src/lib/scrapers/instagram.ts     -> scrapeInstagram(handles[])
 *   - src/lib/scrapers/highlander.ts    -> scrapeHighlanderLink()
 *   - src/lib/scrapers/ucr-events.ts    -> scrapeUcrEventsCalendar()
 *   - src/lib/scrapers/club-sites.ts    -> scrapeClubSites(urls[])
 *
 * Each returns Promise<CampusEvent[]>. A coordinator merges them and
 * writes to the store. This route just reads.
 */
export async function GET() {
  const events = await getEvents();
  return NextResponse.json({ events, count: events.length });
}
