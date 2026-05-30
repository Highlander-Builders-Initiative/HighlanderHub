import { cache } from "react";
import { unstable_cache } from "next/cache";
import type { CampusEvent } from "@/types/event";
import type { EventFilterCountSource } from "@/types/events-feed";
import type { EventRow } from "@/lib/supabase-rows";
import { sanitizePublicEventHost } from "@/lib/events/anonymized-hosts";
import { eventRowToCampusEvent } from "@/lib/events/map-event-row";
import { supabase } from "@/lib/supabase";
import {
  addPacificDays,
  pacificDayKey,
  pacificTodayKey,
  parsePacificDateTimeInput,
  startOfPacificToday,
} from "@/lib/dates";
import {
  coerceCategoryParam,
  coerceDayWindowParam,
  filterEventSource,
  normalizeEventQuery,
  type CategoryValue,
  type DayWindow,
} from "@/components/events/events-filters";
import { PUBLIC_CONTENT_KINDS } from "@/lib/events/content-kind";
import {
  E2E_FIXTURE_EVENTS,
  E2E_PUBLIC_FIXTURE_EVENTS,
  e2eFixturesEnabled,
} from "./fixtures";

const DB_RETRY_ATTEMPTS = 2;
export const EVENTS_PAGE_SIZE = 24;
export const EVENTS_CALENDAR_RANGE_LIMIT = 500;

// Cross-request caching for the public read path. The Supabase client is
// hardwired to `cache: "no-store"` (see lib/supabase.ts), so route-level
// `revalidate` alone can't cache these reads — they're wrapped in the Data
// Cache below instead. Admin mutations call `revalidateTag(EVENTS_CACHE_TAG)`
// to bust every entry; otherwise the stale window is EVENTS_CACHE_TTL_SECONDS.
export const EVENTS_CACHE_TAG = "events";
const EVENTS_CACHE_TTL_SECONDS = 300;
const eventsCacheOptions = {
  revalidate: EVENTS_CACHE_TTL_SECONDS,
  tags: [EVENTS_CACHE_TAG],
};

type EventsPageOptions = {
  limit?: number;
  offset?: number;
  query?: string;
  category?: CategoryValue;
  dayWindow?: DayWindow;
  todayKey?: string;
};

type CalendarEventsOptions = {
  startDayKey: string;
  endDayKey: string;
  limit?: number;
};

type EventFilterCountRow = Pick<
  EventRow,
  | "id"
  | "title"
  | "description"
  | "starts_at"
  | "location"
  | "host"
  | "host_handle"
  | "category"
  | "tags"
>;

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

function toEventFilterCountSource(
  r: EventFilterCountRow
): EventFilterCountSource {
  const { host, hostHandle } = sanitizePublicEventHost(r.host, r.host_handle);
  return {
    id: r.id,
    title: r.title,
    description: r.description,
    startsAt: r.starts_at,
    location: r.location,
    host,
    hostHandle,
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

function hasEventPageFilters({
  query,
  category = "all",
  dayWindow = "all",
}: EventsPageOptions): boolean {
  return (
    normalizeEventQuery(query).length > 0 ||
    coerceCategoryParam(category) !== "all" ||
    coerceDayWindowParam(dayWindow) !== "all"
  );
}

function paginateEvents(
  events: CampusEvent[],
  pageSize: number,
  offset: number
): EventsPageResult {
  const rows = events.slice(offset, offset + pageSize + 1);
  const pageEvents = rows.slice(0, pageSize);
  return {
    events: pageEvents,
    hasMore: rows.length > pageSize,
    nextOffset: offset + pageEvents.length,
  };
}

export function activeEventFilter(nowIso: string): string {
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

function cachePublicRead<Args extends unknown[], Result>(
  operation: (...args: Args) => Promise<Result>,
  keyParts: string[]
): (...args: Args) => Promise<Result> {
  const cached = unstable_cache(operation, keyParts, eventsCacheOptions);
  return (...args: Args) =>
    e2eFixturesEnabled() ? operation(...args) : cached(...args);
}

async function getEventsSummaryUncached(): Promise<EventsSummary> {
  return withE2eFixture(
    () => ({
      total: E2E_PUBLIC_FIXTURE_EVENTS.length,
      upcomingThisWeek: E2E_PUBLIC_FIXTURE_EVENTS.length,
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
              .in("content_kind", PUBLIC_CONTENT_KINDS)
              .or(activeEventFilter(nowIso))
          ),
          withDbRetry("this-week event count", () =>
            supabase
              .from("events")
              .select("id", { count: "exact", head: true })
              .in("content_kind", PUBLIC_CONTENT_KINDS)
              .gte("starts_at", todayIso)
              .lte("starts_at", inSevenDaysIso)
              .or(activeEventFilter(nowIso))
          ),
          withDbRetry("free-food event count", () =>
            supabase
              .from("events")
              .select("id", { count: "exact", head: true })
              .in("content_kind", PUBLIC_CONTENT_KINDS)
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
async function getEventsPageUncached({
  limit = EVENTS_PAGE_SIZE,
  offset = 0,
  query = "",
  category = "all",
  dayWindow = "all",
  todayKey = pacificTodayKey(),
}: EventsPageOptions = {}): Promise<EventsPageResult> {
  const pageSize = Math.max(1, Math.min(limit, 60));
  const from = Math.max(0, offset);
  const normalizedQuery = normalizeEventQuery(query);
  const filters = {
    category: coerceCategoryParam(category),
    dayWindow: coerceDayWindowParam(dayWindow),
    todayKey,
    normalizedQuery,
  };
  const hasFilters = hasEventPageFilters({
    query,
    category: filters.category,
    dayWindow: filters.dayWindow,
  });

  return withE2eFixture(
    () => {
      const source = hasFilters
        ? filterEventSource(E2E_PUBLIC_FIXTURE_EVENTS, filters)
        : E2E_PUBLIC_FIXTURE_EVENTS;
      return paginateEvents(source, pageSize, from);
    },
    async () => {
      const nowIso = new Date().toISOString();

      if (hasFilters) {
        const { data } = await withDbRetry("filtered events", () =>
          supabase
            .from("events")
            .select("*")
            .in("content_kind", PUBLIC_CONTENT_KINDS)
            .or(activeEventFilter(nowIso))
            .order("starts_at", { ascending: true })
            .order("id", { ascending: true })
            .overrideTypes<EventRow[], { merge: false }>()
        );

        const filtered = filterEventSource(
          (data ?? []).map(eventRowToCampusEvent),
          filters
        );
        return paginateEvents(filtered, pageSize, from);
      }

      const to = from + pageSize;

      const { data } = await withDbRetry("events", () =>
        supabase
          .from("events")
          .select("*")
          .in("content_kind", PUBLIC_CONTENT_KINDS)
          .or(activeEventFilter(nowIso))
          // starts_at is not unique; id keeps offset pages from overlapping.
          .order("starts_at", { ascending: true })
          .order("id", { ascending: true })
          .range(from, to)
          .overrideTypes<EventRow[], { merge: false }>()
      );

      const rows = data ?? [];
      const events = rows.slice(0, pageSize).map(eventRowToCampusEvent);

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

async function getEventFilterCountSourceUncached(): Promise<
  EventFilterCountSource[]
> {
  return withE2eFixture(
    () => E2E_PUBLIC_FIXTURE_EVENTS,
    async () => {
      const nowIso = new Date().toISOString();

      const { data } = await withDbRetry("event filter counts", () =>
        supabase
          .from("events")
          .select("id,title,description,starts_at,location,host,host_handle,category,tags")
          .in("content_kind", PUBLIC_CONTENT_KINDS)
          .or(activeEventFilter(nowIso))
          .order("starts_at", { ascending: true })
          .order("id", { ascending: true })
          .overrideTypes<EventFilterCountRow[], { merge: false }>()
      );

      return (data ?? []).map(toEventFilterCountSource);
    }
  );
}

async function getCalendarEventsUncached({
  startDayKey,
  endDayKey,
  limit = EVENTS_CALENDAR_RANGE_LIMIT,
}: CalendarEventsOptions): Promise<CampusEvent[]> {
  return withE2eFixture(
    () =>
      E2E_PUBLIC_FIXTURE_EVENTS.filter((event) => {
        const fixtureDay = pacificDayKey(event.startsAt);
        return fixtureDay >= startDayKey && fixtureDay <= endDayKey;
      }),
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
          .in("content_kind", PUBLIC_CONTENT_KINDS)
          .gte("starts_at", startIso)
          .lt("starts_at", endIso)
          .order("starts_at", { ascending: true })
          .order("id", { ascending: true })
          .limit(Math.max(1, Math.min(limit, EVENTS_CALENDAR_RANGE_LIMIT)))
          .overrideTypes<EventRow[], { merge: false }>()
      );

      return (data ?? []).map(eventRowToCampusEvent);
    }
  );
}

const getEventByIdUncached = cache(async function getEventById(
  id: string
): Promise<CampusEvent | null> {
  // Detail-by-id is intentionally NOT content-kind filtered: a direct deep
  // link to any event still resolves (and admins reach all kinds here),
  // even though fundraiser/other never surface in browse.
  return withE2eFixture(
    () => E2E_FIXTURE_EVENTS.find((event) => event.id === id) ?? null,
    async () => {
      const { data } = await withDbRetry(
        "event",
        () =>
          supabase
            .from("events")
            .select("*")
            .eq("id", id)
            .limit(1)
            .overrideTypes<EventRow[], { merge: false }>(),
        { id }
      );

      const row = data?.[0];
      if (!row) return null;
      return eventRowToCampusEvent(row);
    }
  );
});

// Data Cache wrappers for the public read path. Each keeps the underlying
// function's signature (args are folded into the cache key); a successful
// result is cached for EVENTS_CACHE_TTL_SECONDS and busted by
// revalidateTag(EVENTS_CACHE_TAG). Thrown errors are not cached.
export const getEventsSummary = cachePublicRead(
  getEventsSummaryUncached,
  ["events-summary"]
);
export const getEventsPage = cachePublicRead(
  getEventsPageUncached,
  ["events-page"]
);
export const getEventFilterCountSource = cachePublicRead(
  getEventFilterCountSourceUncached,
  ["event-filter-counts"]
);
export const getCalendarEvents = cachePublicRead(
  getCalendarEventsUncached,
  ["calendar-events"]
);
export const getEventById = cachePublicRead(
  getEventByIdUncached,
  ["event-by-id"]
);
