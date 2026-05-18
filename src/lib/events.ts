import type { CampusEvent } from "@/types/event";
import { supabase } from "@/lib/supabase";
import { startOfPacificToday } from "@/lib/dates";

const DB_RETRY_ATTEMPTS = 2;
export const EVENTS_PAGE_SIZE = 24;

type EventsPageOptions = {
  limit?: number;
  offset?: number;
};

export type EventsPageResult = {
  events: CampusEvent[];
  hasMore: boolean;
  nextOffset: number;
};

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

function describeSupabaseError(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    const message = error.message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return "Unknown Supabase error";
}

function reportDbFailure(
  operation: string,
  error: unknown,
  context?: Record<string, string>
): never {
  const message = describeSupabaseError(error);
  console.error(`[events-db] ${operation} failed`, {
    message,
    ...context,
  });
  throw new Error(`Unable to load ${operation}. Please try again.`, {
    cause: error,
  });
}

async function withDbRetry<T>(
  operation: string,
  query: () => PromiseLike<{ data: T; error: unknown }>,
  context?: Record<string, string>
): Promise<T> {
  let lastError: unknown = null;

  for (let attempt = 1; attempt <= DB_RETRY_ATTEMPTS; attempt += 1) {
    const { data, error } = await query();
    if (!error) return data;

    lastError = error;
    console.warn(`[events-db] ${operation} attempt ${attempt} failed`, {
      message: describeSupabaseError(error),
      ...context,
    });
  }

  reportDbFailure(operation, lastError, context);
}

/**
 * Reads upcoming events from Supabase, sorted by start time ascending.
 * "Upcoming" = starting on or after today (UTC midnight). Past events are
 * filtered out so the list's top row is always the current/next day.
 */
export async function getEventsPage({
  limit = EVENTS_PAGE_SIZE,
  offset = 0,
}: EventsPageOptions = {}): Promise<EventsPageResult> {
  const pageSize = Math.max(1, Math.min(limit, 60));
  const from = Math.max(0, offset);
  const to = from + pageSize;

  const data = await withDbRetry("events", () =>
    supabase
      .from("events")
      .select("*")
      .gte("starts_at", startOfPacificToday().toISOString())
      .order("starts_at", { ascending: true })
      .range(from, to)
  );

  const rows = data as EventRow[];
  const events = rows.slice(0, pageSize).map(toCampusEvent);

  return {
    events,
    hasMore: rows.length > pageSize,
    nextOffset: from + events.length,
  };
}

export async function getEvents(
  options?: EventsPageOptions
): Promise<CampusEvent[]> {
  const page = await getEventsPage(options);
  return page.events;
}

export async function getEventById(id: string): Promise<CampusEvent | null> {
  const data = await withDbRetry(
    "event",
    () =>
      supabase
        .from("events")
        .select("*")
        .eq("id", id)
        .maybeSingle(),
    { id }
  );

  if (!data) return null;
  return toCampusEvent(data as EventRow);
}
