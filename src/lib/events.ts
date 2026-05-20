import { cache } from "react";
import type { CampusEvent } from "@/types/event";
import type { EventRow } from "@/lib/supabase-rows";
import { supabase } from "@/lib/supabase";
import { startOfPacificToday } from "@/lib/dates";
import { normalizeHttpUrl } from "@/lib/event-validation";
import { E2E_FIXTURE_EVENT, e2eFixturesEnabled } from "./events-fixtures";

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

export type EventsSummary = {
  total: number;
  upcomingThisWeek: number;
  freeFood: number;
};

// DB columns are snake_case (Postgres convention); the app uses camelCase
// CampusEvent. EventRow is generated from schemas/events.upsert.schema.json.
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
    sourceUrl: normalizeHttpUrl(r.source_url) ?? undefined,
    imageUrl: normalizeHttpUrl(r.image_url) ?? undefined,
    isFree: r.is_free,
    rsvpRequired: r.rsvp_required,
    rsvpUrl: normalizeHttpUrl(r.rsvp_url) ?? undefined,
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

function activeEventFilter(nowIso: string): string {
  return `ends_at.gte.${nowIso},and(ends_at.is.null,starts_at.gte.${nowIso})`;
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

async function getCount(
  operation: string,
  query: () => PromiseLike<{ count: number | null; error: unknown }>,
  context?: Record<string, string>
): Promise<number> {
  let lastError: unknown = null;

  for (let attempt = 1; attempt <= DB_RETRY_ATTEMPTS; attempt += 1) {
    const { count, error } = await query();
    if (!error) return count ?? 0;

    lastError = error;
    console.warn(`[events-db] ${operation} attempt ${attempt} failed`, {
      message: describeSupabaseError(error),
      ...context,
    });
  }

  reportDbFailure(operation, lastError, context);
}

export async function getEventsSummary(): Promise<EventsSummary> {
  if (e2eFixturesEnabled()) {
    return {
      total: 1,
      upcomingThisWeek: 1,
      freeFood: 0,
    };
  }

  const nowIso = new Date().toISOString();
  const today = startOfPacificToday();
  const todayIso = today.toISOString();
  const inSevenDays = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000);
  const inSevenDaysIso = inSevenDays.toISOString();

  const [total, upcomingThisWeek, freeFood] = await Promise.all([
    getCount("event count", () =>
      supabase
        .from("events")
        .select("id", { count: "exact", head: true })
        .or(activeEventFilter(nowIso))
    ),
    getCount("this-week event count", () =>
      supabase
        .from("events")
        .select("id", { count: "exact", head: true })
        .gte("starts_at", todayIso)
        .lte("starts_at", inSevenDaysIso)
    ),
    getCount("free-food event count", () =>
      supabase
        .from("events")
        .select("id", { count: "exact", head: true })
        .gte("starts_at", todayIso)
        .or('category.eq.free_food,tags.cs.{"free food"}')
    ),
  ]);

  return {
    total,
    upcomingThisWeek,
    freeFood,
  };
}

/**
 * Reads visible events from Supabase, sorted by start time ascending.
 * Events stay visible until their `ends_at` time; if they have no end time,
 * they fall back to `starts_at` so one-off posts still disappear.
 */
export async function getEventsPage({
  limit = EVENTS_PAGE_SIZE,
  offset = 0,
}: EventsPageOptions = {}): Promise<EventsPageResult> {
  if (e2eFixturesEnabled()) {
    const events = offset === 0 && limit > 0 ? [E2E_FIXTURE_EVENT] : [];
    return {
      events,
      hasMore: false,
      nextOffset: events.length,
    };
  }

  const pageSize = Math.max(1, Math.min(limit, 60));
  const from = Math.max(0, offset);
  const to = from + pageSize;
  const nowIso = new Date().toISOString();

  const data = await withDbRetry("events", () =>
    supabase
      .from("events")
      .select("*")
      .or(activeEventFilter(nowIso))
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

export const getEventById = cache(async function getEventById(
  id: string
): Promise<CampusEvent | null> {
  if (e2eFixturesEnabled()) {
    return id === E2E_FIXTURE_EVENT.id ? E2E_FIXTURE_EVENT : null;
  }

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
});
