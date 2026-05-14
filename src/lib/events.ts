import type { CampusEvent } from "@/types/event";
import { supabase } from "@/lib/supabase";
import { startOfPacificToday } from "@/lib/dates";

// DB columns are snake_case (Postgres convention); the app uses camelCase
// CampusEvent. This adapter is the single conversion point.
interface EventRow {
  id: string;
  title: string;
  description: string;
  starts_at: string;
  ends_at: string | null;
  location: string;
  host: string;
  host_handle: string | null;
  category: CampusEvent["category"];
  tags: string[];
  source: CampusEvent["source"];
  source_url: string | null;
  image_url: string | null;
  is_free: boolean;
  rsvp_required: boolean;
  rsvp_url: string | null;
  scraped_at: string;
}

function toCampusEvent(r: EventRow): CampusEvent {
  return {
    id: r.id,
    title: r.title,
    description: r.description,
    startsAt: r.starts_at,
    endsAt: r.ends_at ?? undefined,
    location: r.location,
    host: r.host,
    hostHandle: r.host_handle ?? undefined,
    category: r.category,
    tags: r.tags,
    source: r.source,
    sourceUrl: r.source_url ?? undefined,
    imageUrl: r.image_url ?? undefined,
    isFree: r.is_free,
    rsvpRequired: r.rsvp_required,
    rsvpUrl: r.rsvp_url ?? undefined,
    scrapedAt: r.scraped_at,
  };
}

/**
 * Reads upcoming events from Supabase, sorted by start time ascending.
 * "Upcoming" = starting on or after today (UTC midnight). Past events are
 * filtered out so the list's top row is always the current/next day.
 */
export async function getEvents(): Promise<CampusEvent[]> {
  const { data, error } = await supabase
    .from("events")
    .select("*")
    .gte("starts_at", startOfPacificToday().toISOString())
    .order("starts_at", { ascending: true });

  if (error) {
    console.error("getEvents failed:", error.message);
    return [];
  }
  return (data as EventRow[]).map(toCampusEvent);
}

export async function getEventById(id: string): Promise<CampusEvent | null> {
  const { data, error } = await supabase
    .from("events")
    .select("*")
    .eq("id", id)
    .maybeSingle();

  if (error) {
    console.error("getEventById failed:", error.message);
    return null;
  }
  if (!data) return null;
  return toCampusEvent(data as EventRow);
}
