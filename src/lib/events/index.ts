import { cache } from "react";
import { unstable_cache } from "next/cache";
import type { CampusEvent } from "@/types/event";
import type { EventFeedCursor, EventFilterCountSource } from "@/types/events-feed";
import type { EventRow } from "@/lib/supabase-rows";
import { publicEventHosts } from "@/lib/events/anonymized-hosts";
import { eventRowToCampusEvent } from "@/lib/events/map-event-row";
import { supabase } from "@/lib/supabase";
import {
  addPacificDays,
  pacificDayKey,
  pacificTodayKey,
  parsePacificDateTimeInput,
} from "@/lib/dates";
import {
  coerceCategoryParam,
  coerceDayWindowParam,
  dayWindowRange,
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
const EVENTS_READ_BATCH_SIZE = 500;
const EVENTS_SITEMAP_LIMIT = 500;

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
  /** The last event already loaded; the page starts after it. */
  after?: EventFeedCursor | null;
  query?: string;
  category?: CategoryValue;
  dayWindow?: DayWindow;
  todayKey?: string;
};

type CalendarEventsOptions = {
  startDayKey: string;
  endDayKey: string;
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
  | "hosts"
  | "category"
  | "tags"
  | "has_free_food"
>;

type EventSitemapRow = Pick<EventRow, "id" | "scraped_at">;

export type EventsPageResult = {
  events: CampusEvent[];
  hasMore: boolean;
  /** Pass as `after` for the next page. */
  cursor: EventFeedCursor | null;
};

export type EventSitemapEntry = {
  id: string;
  lastModified: string;
};

function toEventFilterCountSource(
  r: EventFilterCountRow
): EventFilterCountSource {
  const hosts = publicEventHosts(r);
  return {
    id: r.id,
    title: r.title,
    description: r.description,
    startsAt: r.starts_at,
    location: r.location,
    host: hosts.map((entry) => entry.host || entry.hostHandle).join(" & "),
    hostHandle: hosts[0]?.hostHandle,
    hosts,
    category: r.category,
    tags: r.tags,
    hasFreeFood: r.has_free_food,
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

function toCursor(
  event: { startsAt: string; id: string } | undefined,
  fallback: EventFeedCursor | null
): EventFeedCursor | null {
  return event ? { startsAt: event.startsAt, id: event.id } : fallback;
}

/** Index of the first event after `after` in a list in feed order. */
function indexAfter(
  events: { startsAt: string; id: string }[],
  after: EventFeedCursor | null
): number {
  if (!after) return 0;
  const instant = Date.parse(after.startsAt);
  const start = events.findIndex((event) => Date.parse(event.startsAt) >= instant);
  if (start < 0) return events.length;
  // Resume after the cursor's own row. If it is gone, repeat its instant:
  // the client drops the events it already has.
  for (let i = start; i < events.length && Date.parse(events[i].startsAt) === instant; i += 1) {
    if (events[i].id === after.id) return i + 1;
  }
  return start;
}

function paginateEvents(
  events: CampusEvent[],
  pageSize: number,
  after: EventFeedCursor | null
): EventsPageResult {
  const from = indexAfter(events, after);
  const pageEvents = events.slice(from, from + pageSize);
  return {
    events: pageEvents,
    hasMore: events.length > from + pageSize,
    cursor: toCursor(pageEvents.at(-1), after),
  };
}

// Quoted, so an id's dots or a timestamp's colons stay part of the value.
const postgrestValue = (value: string) => `"${value.replace(/[\\"]/g, "\\$&")}"`;

function afterCursorFilter({ startsAt, id }: EventFeedCursor): string {
  const start = postgrestValue(startsAt);
  return `starts_at.gt.${start},and(starts_at.eq.${start},id.gt.${postgrestValue(id)})`;
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

async function getEventsUpcomingThisWeekUncached(): Promise<number> {
  return withE2eFixture(
    () => E2E_PUBLIC_FIXTURE_EVENTS.length,
    async () => {
      const nowIso = new Date().toISOString();
      // "This week" counts exactly what the feed's Week filter shows (today
      // through Saturday), so the number matches the list it links to.
      const week = dayWindowRange("week")!;
      const weekStartIso = parsePacificDateTimeInput(`${week.start}T00:00`);
      const weekEndIso = parsePacificDateTimeInput(
        `${addPacificDays(week.end, 1)}T00:00`
      );
      if (!weekStartIso || !weekEndIso) {
        throw new Error("Unable to load event counts. Invalid week range.");
      }

      const result = await withDbRetry("this-week event count", () =>
        supabase
          .from("events")
          .select("id", { count: "exact", head: true })
          .in("content_kind", PUBLIC_CONTENT_KINDS)
          .gte("starts_at", weekStartIso)
          .lt("starts_at", weekEndIso)
          .or(activeEventFilter(nowIso))
      );
      return result.count ?? 0;
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
  after = null,
  query = "",
  category = "all",
  dayWindow = "all",
  todayKey = pacificTodayKey(),
}: EventsPageOptions = {}): Promise<EventsPageResult> {
  const pageSize = Math.max(1, Math.min(limit, 60));
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
      return paginateEvents(source, pageSize, after);
    },
    async () => {
      const nowIso = new Date().toISOString();

      // Search uses the same sanitized public-host semantics as the browser.
      // Share a complete, narrow source across pages; hydrate only this page.
      if (normalizedQuery) {
        const matches = filterEventSource(await getEventFilterCountSource(), filters);
        const from = indexAfter(matches, after);
        const slice = matches.slice(from, from + pageSize);
        if (!slice.length) return { events: [], hasMore: false, cursor: after };
        const ids = slice.map((event) => event.id);
        const rows = await readEventRows("filtered events", (offset, end) =>
          supabase.from("events").select("*")
            .in("content_kind", PUBLIC_CONTENT_KINDS)
            .or(activeEventFilter(nowIso)).in("id", ids)
            .order("starts_at", { ascending: true }).order("id", { ascending: true })
            .range(offset, end).overrideTypes<EventRow[], { merge: false }>(), ids.length);
        return {
          events: rows.map(eventRowToCampusEvent),
          hasMore: matches.length > from + pageSize,
          // The matched slice, not the hydrated rows: an event that ended
          // since the source was cached must not be requested again.
          cursor: toCursor(slice.at(-1), after),
        };
      }

      const range = dayWindowRange(filters.dayWindow, todayKey);
      const rows = await readEventRows("events", (offset, end) => {
        let request = supabase.from("events").select("*")
          .in("content_kind", PUBLIC_CONTENT_KINDS).or(activeEventFilter(nowIso));
        if (filters.category === "free_food") {
          request = request.or("has_free_food.eq.true,category.eq.free_food");
        } else if (filters.category !== "all") {
          request = request.eq("category", filters.category);
        }
        if (range) {
          request = request.gte("starts_at", parsePacificDateTimeInput(`${range.start}T00:00`)!)
            .lt("starts_at", parsePacificDateTimeInput(`${addPacificDays(range.end, 1)}T00:00`)!);
        }
        if (after) request = request.or(afterCursorFilter(after));
        return request.order("starts_at", { ascending: true })
          .order("id", { ascending: true }).range(offset, end)
          .overrideTypes<EventRow[], { merge: false }>();
      }, pageSize + 1);

      const events = rows.slice(0, pageSize).map(eventRowToCampusEvent);

      return {
        events,
        hasMore: rows.length > pageSize,
        cursor: toCursor(events.at(-1), after),
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

async function readEventRows<T>(
  operation: string,
  query: (from: number, to: number) => PromiseLike<{ data: T[] | null; error: unknown }>,
  maximum = Infinity,
): Promise<T[]> {
  const rows: T[] = [];
  while (rows.length < maximum) {
    const end = Math.min(rows.length + EVENTS_READ_BATCH_SIZE, maximum) - 1;
    const { data } = await withDbRetry(operation, () => query(rows.length, end));
    if (!data?.length) break;
    rows.push(...data);
  }
  return rows;
}

async function getEventFilterCountSourceUncached(): Promise<
  EventFilterCountSource[]
> {
  return withE2eFixture(
    () => E2E_PUBLIC_FIXTURE_EVENTS,
    async () => {
      const nowIso = new Date().toISOString();

      const rows = await readEventRows("event filter counts", (from, to) =>
        supabase
          .from("events")
          .select("id,title,description,starts_at,location,host,host_handle,hosts,category,tags,has_free_food")
          .in("content_kind", PUBLIC_CONTENT_KINDS)
          .or(activeEventFilter(nowIso))
          .order("starts_at", { ascending: true })
          .order("id", { ascending: true })
          .range(from, to)
          .overrideTypes<EventFilterCountRow[], { merge: false }>()
      );

      return rows.map(toEventFilterCountSource);
    }
  );
}

async function getSitemapEventsUncached(): Promise<EventSitemapEntry[]> {
  return withE2eFixture(
    () =>
      E2E_PUBLIC_FIXTURE_EVENTS.map((event) => ({
        id: event.id,
        lastModified: event.scrapedAt,
      })),
    async () => {
      const nowIso = new Date().toISOString();

      const { data } = await withDbRetry("sitemap events", () =>
        supabase
          .from("events")
          .select("id,starts_at,scraped_at")
          .in("content_kind", PUBLIC_CONTENT_KINDS)
          .or(activeEventFilter(nowIso))
          .order("starts_at", { ascending: true })
          .order("id", { ascending: true })
          .limit(EVENTS_SITEMAP_LIMIT)
          .overrideTypes<EventSitemapRow[], { merge: false }>()
      );

      return (data ?? []).map((event) => ({
        id: event.id,
        lastModified: event.scraped_at,
      }));
    }
  );
}

async function getCalendarEventsUncached({
  startDayKey,
  endDayKey,
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

      const rows = await readEventRows("calendar events", (from, to) =>
        supabase
          .from("events")
          .select("*")
          .in("content_kind", PUBLIC_CONTENT_KINDS)
          .gte("starts_at", startIso)
          .lt("starts_at", endIso)
          .order("starts_at", { ascending: true })
          .order("id", { ascending: true })
          .range(from, to)
          .overrideTypes<EventRow[], { merge: false }>()
      );

      return rows.map(eventRowToCampusEvent);
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
export const getEventsUpcomingThisWeek = cachePublicRead(
  getEventsUpcomingThisWeekUncached,
  ["events-upcoming-this-week"]
);
export const getEventsPage = cachePublicRead(
  getEventsPageUncached,
  ["events-page"]
);
export const getEventFilterCountSource = cachePublicRead(
  getEventFilterCountSourceUncached,
  ["event-filter-counts"]
);
export const getSitemapEvents = cachePublicRead(
  getSitemapEventsUncached,
  ["sitemap-events"]
);
export const getCalendarEvents = cachePublicRead(
  getCalendarEventsUncached,
  ["calendar-events"]
);
export const getEventById = cachePublicRead(
  getEventByIdUncached,
  ["event-by-id"]
);
