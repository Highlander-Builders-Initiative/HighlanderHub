import { cache } from "react";
import type { CampusEvent } from "@/types/event";
import type { EventFilterCountSource } from "@/types/events-feed";
import type { EventRow } from "@/lib/supabase-rows";
import { supabase } from "@/lib/supabase";
import {
  addPacificDays,
  pacificDayKey,
  parsePacificDateTimeInput,
  startOfPacificToday,
} from "@/lib/dates";
import { normalizeHttpUrl } from "@/lib/events/validation";
import { E2E_FIXTURE_EVENT, e2eFixturesEnabled } from "./fixtures";

const DB_RETRY_ATTEMPTS = 2;
export const EVENTS_PAGE_SIZE = 24;
export const EVENTS_CALENDAR_RANGE_LIMIT = 500;

type EventsPageOptions = {
  limit?: number;
  offset?: number;
};

type CalendarEventsOptions = {
  startDayKey: string;
  endDayKey: string;
  limit?: number;
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

function toEventFilterCountSource(r: EventRow): EventFilterCountSource {
  return {
    id: r.id,
    title: r.title,
    description: r.description,
    startsAt: r.starts_at,
    location: r.location,
    host: r.host,
    category: r.category,
    tags: r.tags,
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

function withE2eFixture<T>(
  fixture: () => T,
  production: () => Promise<T>
): Promise<T> {
  if (e2eFixturesEnabled()) {
    return Promise.resolve(fixture());
  }

  return production();
}

async function withDbRetry<T extends { error: unknown }>(
  operation: string,
  query: () => PromiseLike<T>,
  context?: Record<string, string>
): Promise<T> {
  let lastError: unknown = null;

  for (let attempt = 1; attempt <= DB_RETRY_ATTEMPTS; attempt += 1) {
    const result = await query();
    if (!result.error) return result;

    lastError = result.error;
    console.warn(`[events-db] ${operation} attempt ${attempt} failed`, {
      message: describeSupabaseError(result.error),
      ...context,
    });
  }

  reportDbFailure(operation, lastError, context);
}

export async function getEventsSummary(): Promise<EventsSummary> {
  return withE2eFixture(
    () => ({
      total: 1,
      upcomingThisWeek: 1,
      freeFood: 0,
    }),
    async () => {
      const nowIso = new Date().toISOString();
      const today = startOfPacificToday();
      const todayIso = today.toISOString();
      const inSevenDays = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000);
      const inSevenDaysIso = inSevenDays.toISOString();

      const [totalResult, upcomingThisWeekResult, freeFoodResult] =
        await Promise.all([
          withDbRetry("event count", () =>
            supabase
              .from("events")
              .select("id", { count: "exact", head: true })
              .or(activeEventFilter(nowIso))
          ),
          withDbRetry("this-week event count", () =>
            supabase
              .from("events")
              .select("id", { count: "exact", head: true })
              .gte("starts_at", todayIso)
              .lte("starts_at", inSevenDaysIso)
              .or(activeEventFilter(nowIso))
          ),
          withDbRetry("free-food event count", () =>
            supabase
              .from("events")
              .select("id", { count: "exact", head: true })
              .gte("starts_at", todayIso)
              .or('category.eq.free_food,tags.cs.{"free food"}')
          ),
        ]);

      return {
        total: totalResult.count ?? 0,
        upcomingThisWeek: upcomingThisWeekResult.count ?? 0,
        freeFood: freeFoodResult.count ?? 0,
      };
    }
  );
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
  return withE2eFixture(
    () => {
      const events = offset === 0 && limit > 0 ? [E2E_FIXTURE_EVENT] : [];
      return {
        events,
        hasMore: false,
        nextOffset: events.length,
      };
    },
    async () => {
      const pageSize = Math.max(1, Math.min(limit, 60));
      const from = Math.max(0, offset);
      const to = from + pageSize;
      const nowIso = new Date().toISOString();

      const { data } = await withDbRetry("events", () =>
        supabase
          .from("events")
          .select("*")
          .or(activeEventFilter(nowIso))
          // starts_at is not unique; id keeps offset pages from overlapping.
          .order("starts_at", { ascending: true })
          .order("id", { ascending: true })
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
  );
}

export async function getEvents(
  options?: EventsPageOptions
): Promise<CampusEvent[]> {
  const page = await getEventsPage(options);
  return page.events;
}

export async function getEventFilterCountSource(): Promise<
  EventFilterCountSource[]
> {
  return withE2eFixture(
    () => [E2E_FIXTURE_EVENT],
    async () => {
      const nowIso = new Date().toISOString();

      const { data } = await withDbRetry("event filter counts", () =>
        supabase
          .from("events")
          .select("id,title,description,starts_at,location,host,category,tags")
          .or(activeEventFilter(nowIso))
          .order("starts_at", { ascending: true })
          .order("id", { ascending: true })
      );

      return (data as EventRow[]).map(toEventFilterCountSource);
    }
  );
}

export async function getCalendarEvents({
  startDayKey,
  endDayKey,
  limit = EVENTS_CALENDAR_RANGE_LIMIT,
}: CalendarEventsOptions): Promise<CampusEvent[]> {
  return withE2eFixture(
    () => {
      const fixtureDay = pacificDayKey(E2E_FIXTURE_EVENT.startsAt);
      return fixtureDay >= startDayKey && fixtureDay <= endDayKey
        ? [E2E_FIXTURE_EVENT]
        : [];
    },
    async () => {
      const startIso = parsePacificDateTimeInput(`${startDayKey}T00:00`);
      const endIso = parsePacificDateTimeInput(
        `${addPacificDays(endDayKey, 1)}T00:00`
      );
      if (!startIso || !endIso) {
        throw new Error("Unable to load calendar events. Invalid date range.");
      }

      const { data } = await withDbRetry("calendar events", () =>
        supabase
          .from("events")
          .select("*")
          .gte("starts_at", startIso)
          .lt("starts_at", endIso)
          .order("starts_at", { ascending: true })
          .order("id", { ascending: true })
          .limit(Math.max(1, Math.min(limit, EVENTS_CALENDAR_RANGE_LIMIT)))
      );

      return (data as EventRow[]).map(toCampusEvent);
    }
  );
}

export const getEventById = cache(async function getEventById(
  id: string
): Promise<CampusEvent | null> {
  return withE2eFixture(
    () => (id === E2E_FIXTURE_EVENT.id ? E2E_FIXTURE_EVENT : null),
    async () => {
      const { data } = await withDbRetry(
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
  );
});
