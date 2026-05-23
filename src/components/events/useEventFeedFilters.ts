"use client";

import { useMemo } from "react";
import type { CampusEvent, EventCategory } from "@/types/event";
import type { EventFilterCountSource } from "@/types/events-feed";
import { getEmptyFeedCopy } from "@/lib/events/empty-feed-copy";
import { groupByDay } from "@/lib/events/grouping";
import {
  CATEGORIES,
  matchesCategory,
  matchesDayWindow,
  type CategoryValue,
  type DayWindow,
} from "./events-filters";

function buildEventSearchText(event: EventFilterCountSource) {
  return [event.title, event.description, event.host, event.location, ...event.tags]
    .join(" ")
    .toLowerCase();
}

type UseEventFeedFiltersArgs = {
  loadedEvents: CampusEvent[];
  filterCountSource: EventFilterCountSource[];
  calendarEvents?: CampusEvent[];
  category: CategoryValue;
  query: string;
  dayWindow: DayWindow;
  todayKey: string;
};

export type EventFeedActiveFilters = {
  query: string;
  hasQuery: boolean;
  category: CategoryValue;
  hasCategory: boolean;
  dayWindow: DayWindow;
  hasDayWindow: boolean;
  hasAny: boolean;
};

export function useEventFeedFilters({
  loadedEvents,
  filterCountSource,
  calendarEvents,
  category,
  query,
  dayWindow,
  todayKey,
}: UseEventFeedFiltersArgs) {
  const trimmedQuery = query.trim();
  const normalizedQuery = trimmedQuery.toLowerCase();
  const activeFilters = useMemo<EventFeedActiveFilters>(() => {
    const hasQuery = trimmedQuery.length > 0;
    const hasCategory = category !== "all";
    const hasDayWindow = dayWindow !== "all";
    return {
      query: trimmedQuery,
      hasQuery,
      category,
      hasCategory,
      dayWindow,
      hasDayWindow,
      hasAny: hasQuery || hasCategory || hasDayWindow,
    };
  }, [category, dayWindow, trimmedQuery]);
  const emptyCopy = useMemo(
    () => getEmptyFeedCopy(activeFilters),
    [activeFilters]
  );

  const eventSearchText = useMemo(
    () => loadedEvents.map(buildEventSearchText),
    [loadedEvents]
  );
  const countSourceSearchText = useMemo(
    () => filterCountSource.map(buildEventSearchText),
    [filterCountSource]
  );
  const calendarSourceEvents = calendarEvents ?? loadedEvents;
  const calendarSearchText = useMemo(
    () => calendarSourceEvents.map(buildEventSearchText),
    [calendarSourceEvents]
  );

  const filteredExceptCategory = useMemo(() => {
    return loadedEvents.filter((ev, index) => {
      if (normalizedQuery && !eventSearchText[index].includes(normalizedQuery)) {
        return false;
      }
      if (!matchesDayWindow(ev, dayWindow, todayKey)) return false;
      return true;
    });
  }, [loadedEvents, normalizedQuery, eventSearchText, dayWindow, todayKey]);

  const countSourceExceptCategory = useMemo(() => {
    return filterCountSource.filter((ev, index) => {
      if (
        normalizedQuery &&
        !countSourceSearchText[index].includes(normalizedQuery)
      ) {
        return false;
      }
      if (!matchesDayWindow(ev, dayWindow, todayKey)) return false;
      return true;
    });
  }, [
    filterCountSource,
    normalizedQuery,
    countSourceSearchText,
    dayWindow,
    todayKey,
  ]);

  const filteredCalendarEvents = useMemo(() => {
    return calendarSourceEvents.filter((ev, index) => {
      if (
        normalizedQuery &&
        !calendarSearchText[index].includes(normalizedQuery)
      ) {
        return false;
      }
      if (!matchesDayWindow(ev, dayWindow, todayKey)) return false;
      if (!matchesCategory(ev, category)) return false;
      return true;
    });
  }, [
    calendarSourceEvents,
    normalizedQuery,
    calendarSearchText,
    dayWindow,
    todayKey,
    category,
  ]);

  const filtered = useMemo(() => {
    return filteredExceptCategory.filter((ev) => matchesCategory(ev, category));
  }, [filteredExceptCategory, category]);

  const counts = useMemo(() => {
    const map = new Map<CategoryValue, number>();
    map.set("all", countSourceExceptCategory.length);
    for (const c of CATEGORIES) {
      if (c.value === "all") continue;
      map.set(
        c.value,
        countSourceExceptCategory.filter((ev) => matchesCategory(ev, c.value)).length
      );
    }
    return map;
  }, [countSourceExceptCategory]);

  const grouped = useMemo(() => groupByDay(filtered), [filtered]);
  const calendarGrouped = useMemo(
    () => groupByDay(filteredCalendarEvents),
    [filteredCalendarEvents]
  );
  const dayKeys = Array.from(grouped.keys());

  const categoriesByDay = useMemo(() => {
    const map = new Map<string, EventCategory[]>();
    for (const [key, evs] of calendarGrouped) {
      const seen = new Set<EventCategory>();
      const ordered: EventCategory[] = [];
      for (const ev of evs) {
        if (!seen.has(ev.category)) {
          seen.add(ev.category);
          ordered.push(ev.category);
        }
      }
      map.set(key, ordered);
    }
    return map;
  }, [calendarGrouped]);

  const hasActiveFilters = activeFilters.hasAny;

  const loadedTotal = filtered.length;
  const feedTotal = filterCountSource.length;
  const resultsLabel = hasActiveFilters
    ? `${filtered.length} matching ${filtered.length === 1 ? "event" : "events"}`
    : loadedTotal === feedTotal
      ? `${loadedTotal} ${loadedTotal === 1 ? "event" : "events"} loaded`
    : `${filtered.length} of ${feedTotal} ${feedTotal === 1 ? "event" : "events"} loaded`;

  const activeFilterCount =
    (activeFilters.hasCategory ? 1 : 0) +
    (activeFilters.hasDayWindow ? 1 : 0);

  return {
    trimmedQuery,
    activeFilters,
    emptyCopy,
    filteredExceptCategory,
    filtered,
    counts,
    grouped,
    dayKeys,
    categoriesByDay,
    hasActiveFilters,
    resultsLabel,
    activeFilterCount,
  };
}
