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
import { DAY_WINDOWS, type DayWindow } from "@/types/events-feed";

export type CategoryValue = EventCategory | "all";

// Free Food leads the browse list (just after "All") since it's the
// highest-intent filter for students; the rest follow EVENT_CATEGORIES order.
const RAIL_CATEGORY_ORDER: EventCategory[] = [
  "free_food",
  ...EVENT_CATEGORIES.filter((value) => value !== "free_food"),
];

export const CATEGORIES: { value: CategoryValue; label: string }[] = [
  { value: "all", label: "All" },
  ...RAIL_CATEGORY_ORDER.map((value) => ({
    value,
    label:
      value === "club"
        ? "Clubs"
        : value === "free_food"
          ? "Free Food"
          : EVENT_CATEGORY_LABELS[value].split(" / ")[0],
  })),
];

export { DAY_WINDOWS };
export type { DayWindow };

export function categoryLabel(value: CategoryValue): string {
  return CATEGORIES.find((c) => c.value === value)?.label ?? "All";
}

export function dayWindowLabel(value: DayWindow): string {
  return DAY_WINDOWS.find((w) => w.value === value)?.label ?? "";
}

export function dayWindowPhrase(value: DayWindow): string {
  return DAY_WINDOWS.find((w) => w.value === value)?.phrase ?? "";
}

/**
 * Coerce a raw URL search-param value into a known CategoryValue. Unknown or
 * missing values fall back to "all"; the URL is the only untrusted input here,
 * so we never let it widen the filter beyond what the rail can show.
 */
export function coerceCategoryParam(
  raw: string | undefined | null
): CategoryValue {
  if (!raw) return "all";
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

export function matchesCategory(
  ev: Pick<CampusEvent, "category" | "hasFreeFood">,
  cat: CategoryValue
): boolean {
  if (cat === "all") return true;
  if (cat === "free_food") {
    // Free food is its own attribute now; `category === "free_food"` only
    // matches legacy rows predating the split (kept until they expire).
    return ev.hasFreeFood || ev.category === "free_food";
  }
  return ev.category === cat;
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
  "title" | "description" | "host" | "hostHandle" | "location" | "tags"
>;

type EventFilterable = SearchableEvent &
  Pick<CampusEvent, "startsAt" | "category" | "tags" | "hasFreeFood">;

export type EventFilterCriteria = {
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
  return (query ?? "").trim().toLowerCase();
}

export function matchesEventFilters(
  event: EventFilterable,
  filters: EventFilterCriteria,
  options: {
    includeCategory?: boolean;
    searchText?: string;
  } = {}
): boolean {
  const normalizedQuery =
    filters.normalizedQuery ?? normalizeEventQuery(filters.query);
  const searchText = options.searchText ?? buildEventSearchText(event);

  if (!matchesQuery(searchText, normalizedQuery)) return false;
  if (!matchesDayWindow(event, filters.dayWindow, filters.todayKey)) return false;
  if (options.includeCategory !== false && !matchesCategory(event, filters.category)) {
    return false;
  }
  return true;
}

export function filterEventSource<T extends EventFilterable>(
  events: T[],
  filters: EventFilterCriteria,
  options: {
    includeCategory?: boolean;
    searchText?: string[];
  } = {}
): T[] {
  return events.filter((event, index) =>
    matchesEventFilters(event, filters, {
      includeCategory: options.includeCategory,
      searchText: options.searchText?.[index],
    })
  );
}

export function countEventsByCategory<T extends Pick<CampusEvent, "category" | "hasFreeFood">>(
  events: T[]
): Map<CategoryValue, number> {
  const map = new Map<CategoryValue, number>();
  map.set("all", events.length);
  for (const c of CATEGORIES) {
    if (c.value === "all") continue;
    map.set(c.value, events.filter((ev) => matchesCategory(ev, c.value)).length);
  }
  return map;
}
