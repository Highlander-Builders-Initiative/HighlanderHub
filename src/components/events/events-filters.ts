import {
  EVENT_CATEGORIES,
  EVENT_CATEGORY_LABELS,
  type CampusEvent,
  type EventCategory,
} from "@/types/event";
import {
  addPacificDays,
  pacificDayKey,
  pacificTodayKey,
  pacificWeekdayIndex,
} from "@/lib/dates";
import { isDeadlineKind } from "@/lib/events/content-kind";
import {
  HOST_GROUPS,
  coerceHostGroupParam,
  hostGroupLabel,
  matchesHostGroup,
  type HostGroupValue,
} from "@/lib/host-groups";
import { DAY_WINDOWS, type DayWindow } from "@/types/events-feed";

/** An activity the Topics rail lists: every category but `other`. */
export type TopicCategory = Exclude<EventCategory, "other">;
export type CategoryValue = TopicCategory | "all";

export const CATEGORIES: { value: CategoryValue; label: string }[] = [
  { value: "all", label: "All" },
  ...EVENT_CATEGORIES.filter(
    (value): value is TopicCategory => value !== "other"
  ).map((value) => ({ value, label: EVENT_CATEGORY_LABELS[value] })),
];

export { DAY_WINDOWS };
export type { DayWindow };

/**
 * The feed's filters, one per independent question: what you'd be doing
 * (category), when, whether there's free food, deadlines only, and who hosts.
 * Free food and deadlines combine with any topic instead of replacing it.
 */
export type EventFeedFacets = {
  freeFood: boolean;
  deadlines: boolean;
  hostGroup: HostGroupValue;
};

/** The fields that identify a paged event list. Its cursor belongs to them. */
export type EventFeedQuery = EventFeedFacets & {
  query: string;
  category: CategoryValue;
  dayWindow: DayWindow;
};

export const NO_FEED_FACETS: EventFeedFacets = {
  freeFood: false,
  deadlines: false,
  hostGroup: "all",
};

export const DEFAULT_EVENT_FEED_QUERY: EventFeedQuery = {
  query: "",
  category: "all",
  dayWindow: "all",
  ...NO_FEED_FACETS,
};

export function eventFeedQueriesEqual(
  a: EventFeedQuery,
  b: EventFeedQuery
): boolean {
  return (
    a.category === b.category &&
    a.dayWindow === b.dayWindow &&
    a.freeFood === b.freeFood &&
    a.deadlines === b.deadlines &&
    a.hostGroup === b.hostGroup &&
    a.query.trim() === b.query.trim()
  );
}

export function categoryLabel(value: CategoryValue): string {
  return CATEGORIES.find((c) => c.value === value)?.label ?? "All";
}

export function dayWindowLabel(value: DayWindow): string {
  return DAY_WINDOWS.find((w) => w.value === value)?.label ?? "";
}

export function dayWindowPhrase(value: DayWindow): string {
  return DAY_WINDOWS.find((w) => w.value === value)?.phrase ?? "";
}

export { hostGroupLabel };

// Topics links shared before the activity categories: each old topic opens
// the one that took its place. Free food is its own switch now (see
// readEventFeedQuery).
const LEGACY_CATEGORY_PARAMS: Record<string, TopicCategory> = {
  social: "hangout",
  club: "get_involved",
  community: "volunteering",
};

/**
 * Coerce a raw URL search-param value into a known CategoryValue. Unknown or
 * missing values fall back to "all"; the URL is the only untrusted input here,
 * so we never let it widen the filter beyond what the rail can show.
 */
export function coerceCategoryParam(
  raw: string | undefined | null
): CategoryValue {
  if (!raw) return "all";
  if (Object.hasOwn(LEGACY_CATEGORY_PARAMS, raw)) return LEGACY_CATEGORY_PARAMS[raw];
  return CATEGORIES.some((c) => c.value === raw)
    ? (raw as CategoryValue)
    : "all";
}

export function coerceDayWindowParam(
  raw: string | undefined | null
): DayWindow {
  if (!raw) return "all";
  return DAY_WINDOWS.some((w) => w.value === raw)
    ? (raw as DayWindow)
    : "all";
}

/**
 * The feed's query from its URL: ?cat=&q=&when=&food=1&deadlines=1&host=.
 * `get` reads one parameter, so both a page's searchParams and a route's
 * URLSearchParams can supply it.
 */
export function readEventFeedQuery(
  get: (key: string) => string | undefined | null
): EventFeedQuery {
  const cat = get("cat");
  return {
    query: get("q") ?? "",
    category: coerceCategoryParam(cat),
    dayWindow: coerceDayWindowParam(get("when")),
    freeFood: get("food") === "1" || cat === "free_food",
    deadlines: get("deadlines") === "1",
    hostGroup: coerceHostGroupParam(get("host")),
  };
}

/** The inverse of readEventFeedQuery; default filters are left out. */
export function eventFeedSearchParams(filters: EventFeedQuery): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.category !== "all") params.set("cat", filters.category);
  if (filters.query.trim()) params.set("q", filters.query.trim());
  if (filters.dayWindow !== "all") params.set("when", filters.dayWindow);
  if (filters.freeFood) params.set("food", "1");
  if (filters.deadlines) params.set("deadlines", "1");
  if (filters.hostGroup !== "all") params.set("host", filters.hostGroup);
  return params;
}

/** An /events link with these filters, for links into the feed. */
export function eventsFeedHref(filters: Partial<EventFeedQuery>): string {
  const search = eventFeedSearchParams({ ...DEFAULT_EVENT_FEED_QUERY, ...filters }).toString();
  return search ? `/events?${search}` : "/events";
}

/** How the desktop feed lists events: flyer cards, or a compact row list. */
export type FeedView = "cards" | "compact";

/** Cookie that remembers the desktop feed view, read on the server so the
 *  first paint is already in the chosen view. */
export const FEED_VIEW_COOKIE = "hh_feed_view";

export function coerceFeedView(raw: string | undefined | null): FeedView {
  return raw === "compact" ? "compact" : "cards";
}

export function matchesCategory(
  ev: Pick<CampusEvent, "category">,
  cat: CategoryValue
): boolean {
  return cat === "all" || ev.category === cat;
}

/**
 * Returns the inclusive Pacific day-key range for a given window, anchored at
 * today. Returns null for "all" (no date constraint).
 */
export function dayWindowRange(
  window: DayWindow,
  today = pacificTodayKey()
): { start: string; end: string } | null {
  if (window === "all") return null;
  if (window === "today") return { start: today, end: today };
  if (window === "week") {
    // ISO-ish week starting Sunday (matches the calendar grid). Last day is
    // Saturday.
    const weekday = pacificWeekdayIndex(today); // 0=Sun
    const start = addPacificDays(today, -weekday);
    const end = addPacificDays(start, 6);
    // But "this week" should not include past days; pin start to today.
    return { start: today > start ? today : start, end };
  }
  // weekend: next Saturday + Sunday (or current weekend if today is Sat/Sun).
  const weekday = pacificWeekdayIndex(today);
  if (weekday === 0) return { start: today, end: today };
  if (weekday === 6) return { start: today, end: addPacificDays(today, 1) };
  const daysUntilSat = 6 - weekday;
  const start = addPacificDays(today, daysUntilSat);
  const end = addPacificDays(start, 1);
  return { start, end };
}

export function matchesDayWindow(
  ev: Pick<CampusEvent, "startsAt">,
  window: DayWindow,
  today = pacificTodayKey()
): boolean {
  const range = dayWindowRange(window, today);
  if (!range) return true;
  const key = pacificDayKey(ev.startsAt);
  return key >= range.start && key <= range.end;
}

type SearchableEvent = Pick<
  CampusEvent,
  "title" | "description" | "host" | "hostHandle" | "hosts" | "location" | "tags"
>;

type EventFilterable = SearchableEvent &
  Pick<CampusEvent, "startsAt" | "category" | "tags" | "hasFreeFood" | "contentKind">;

/** One filter the feed counts separately: each count applies all the others. */
export type EventFeedFacet = "category" | "freeFood" | "deadlines" | "hostGroup";

export type EventFilterCriteria = Partial<EventFeedFacets> & {
  category: CategoryValue;
  dayWindow: DayWindow;
  todayKey: string;
  query?: string;
  normalizedQuery?: string;
};

/** Flattened, lowercased haystack for substring search across an event's
 * title, description, host, handle, location, and tags. */
export function buildEventSearchText(event: SearchableEvent): string {
  return [
    event.title,
    event.description,
    event.host,
    event.hostHandle ?? "",
    ...(event.hosts ?? []).flatMap((host) => [host.host, host.hostHandle ?? ""]),
    event.location,
    ...event.tags,
  ]
    .join(" ")
    .toLowerCase();
}

export function matchesQuery(searchText: string, normalizedQuery: string) {
  return normalizedQuery.length === 0 || searchText.includes(normalizedQuery);
}

export function normalizeEventQuery(query: string | undefined): string {
  return (query ?? "").trim().replace(/^@/, "").toLowerCase();
}

export function matchesEventFilters(
  event: EventFilterable,
  filters: EventFilterCriteria,
  options: {
    /** Leave this filter out, to count what choosing it would show. */
    except?: EventFeedFacet;
    searchText?: string;
  } = {}
): boolean {
  const normalizedQuery =
    filters.normalizedQuery ?? normalizeEventQuery(filters.query);
  const searchText = options.searchText ?? buildEventSearchText(event);
  const { except } = options;

  if (!matchesQuery(searchText, normalizedQuery)) return false;
  if (!matchesDayWindow(event, filters.dayWindow, filters.todayKey)) return false;
  if (except !== "category" && !matchesCategory(event, filters.category)) return false;
  if (except !== "freeFood" && filters.freeFood && !event.hasFreeFood) return false;
  if (except !== "deadlines" && filters.deadlines && !isDeadlineKind(event.contentKind)) {
    return false;
  }
  if (except !== "hostGroup" && !matchesHostGroup(event, filters.hostGroup ?? "all")) {
    return false;
  }
  return true;
}

export function filterEventSource<T extends EventFilterable>(
  events: T[],
  filters: EventFilterCriteria,
  options: {
    except?: EventFeedFacet;
    searchText?: string[];
  } = {}
): T[] {
  return events.filter((event, index) =>
    matchesEventFilters(event, filters, {
      except: options.except,
      searchText: options.searchText?.[index],
    })
  );
}

/** What each Topics row, switch and Hosted by row would show if chosen. */
export type EventFacetCounts = {
  categories: Map<CategoryValue, number>;
  freeFood: number;
  deadlines: number;
  hostGroups: Map<HostGroupValue, number>;
};

export const EMPTY_FACET_COUNTS: EventFacetCounts = {
  categories: new Map(),
  freeFood: 0,
  deadlines: 0,
  hostGroups: new Map(),
};

export function countEventFacets<T extends EventFilterable>(
  events: T[],
  filters: EventFilterCriteria,
  searchText?: string[]
): EventFacetCounts {
  const except = (facet: EventFeedFacet) =>
    filterEventSource(events, filters, { except: facet, searchText });

  const byCategory = except("category");
  const categories = new Map<CategoryValue, number>();
  for (const c of CATEGORIES) {
    categories.set(
      c.value,
      byCategory.filter((ev) => matchesCategory(ev, c.value)).length
    );
  }

  const byHost = except("hostGroup");
  const hostGroups = new Map<HostGroupValue, number>([["all", byHost.length]]);
  for (const ev of byHost) {
    for (const { value } of HOST_GROUPS) {
      if (matchesHostGroup(ev, value)) {
        hostGroups.set(value, (hostGroups.get(value) ?? 0) + 1);
      }
    }
  }

  return {
    categories,
    freeFood: except("freeFood").filter((ev) => ev.hasFreeFood).length,
    deadlines: except("deadlines").filter((ev) => isDeadlineKind(ev.contentKind)).length,
    hostGroups,
  };
}
