"use client";

import { useMemo } from "react";
import type { CampusEvent } from "@/types/event";
import type { EventFilterCountSource } from "@/types/events-feed";
import { getEmptyFeedCopy } from "@/lib/events/empty-feed-copy";
import { groupByDay } from "@/lib/events/grouping";
import {
  buildEventSearchText,
  countEventFacets,
  filterEventSource,
  normalizeEventQuery,
  type CategoryValue,
  type DayWindow,
  type EventFeedFacets,
} from "./events-filters";
import type { HostGroupValue } from "@/lib/host-groups";

type UseEventFeedFiltersArgs = Partial<EventFeedFacets> & {
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
  freeFood: boolean;
  deadlines: boolean;
  hostGroup: HostGroupValue;
  hasHostGroup: boolean;
  hasAny: boolean;
};

export function useEventFeedFilters({
  loadedEvents,
  filterCountSource,
  calendarEvents,
  category,
  query,
  dayWindow,
  freeFood = false,
  deadlines = false,
  hostGroup = "all",
  todayKey,
}: UseEventFeedFiltersArgs) {
  const trimmedQuery = query.trim();
  const normalizedQuery = normalizeEventQuery(trimmedQuery);
  const activeFilters = useMemo<EventFeedActiveFilters>(() => {
    const hasQuery = trimmedQuery.length > 0;
    const hasCategory = category !== "all";
    const hasDayWindow = dayWindow !== "all";
    const hasHostGroup = hostGroup !== "all";
    return {
      query: trimmedQuery,
      hasQuery,
      category,
      hasCategory,
      dayWindow,
      hasDayWindow,
      freeFood,
      deadlines,
      hostGroup,
      hasHostGroup,
      hasAny:
        hasQuery || hasCategory || hasDayWindow || freeFood || deadlines || hasHostGroup,
    };
  }, [category, dayWindow, freeFood, deadlines, hostGroup, trimmedQuery]);
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
  const filters = useMemo(
    () => ({ category, dayWindow, freeFood, deadlines, hostGroup, todayKey, normalizedQuery }),
    [category, dayWindow, freeFood, deadlines, hostGroup, todayKey, normalizedQuery]
  );

  const filtered = useMemo(() => {
    return filterEventSource(loadedEvents, filters, {
      searchText: eventSearchText,
    });
  }, [loadedEvents, filters, eventSearchText]);

  const filteredCalendarEvents = useMemo(() => {
    return filterEventSource(calendarSourceEvents, filters, {
      searchText: calendarSearchText,
    });
  }, [calendarSourceEvents, filters, calendarSearchText]);

  // Each row counts the full source with every other filter applied, so a
  // number is what choosing that row would show.
  const counts = useMemo(() => {
    return countEventFacets(filterCountSource, filters, countSourceSearchText);
  }, [filterCountSource, filters, countSourceSearchText]);

  const grouped = useMemo(() => groupByDay(filtered), [filtered]);
  const calendarGrouped = useMemo(
    () => groupByDay(filteredCalendarEvents),
    [filteredCalendarEvents]
  );
  const dayKeys = useMemo(() => Array.from(grouped.keys()), [grouped]);

  // Per-day event count: the calendar marks days that have events, and each
  // day's button announces its count.
  const countsByDay = useMemo(() => {
    const map = new Map<string, number>();
    for (const [key, evs] of calendarGrouped) {
      map.set(key, evs.length);
    }
    return map;
  }, [calendarGrouped]);

  const hasActiveFilters = activeFilters.hasAny;

  const loadedTotal = filtered.length;
  const feedTotal = filterCountSource.length;
  const matchingTotal = counts.categories.get(category) ?? 0;
  const resultsLabel = hasActiveFilters
    ? `${matchingTotal} matching ${matchingTotal === 1 ? "event" : "events"}`
    : loadedTotal === feedTotal
      ? `${loadedTotal} ${loadedTotal === 1 ? "event" : "events"} loaded`
    : `${filtered.length} of ${feedTotal} ${feedTotal === 1 ? "event" : "events"} loaded`;

  const activeFilterCount =
    (activeFilters.hasCategory ? 1 : 0) +
    (activeFilters.hasDayWindow ? 1 : 0) +
    (freeFood ? 1 : 0) +
    (deadlines ? 1 : 0) +
    (activeFilters.hasHostGroup ? 1 : 0);

  return {
    trimmedQuery,
    activeFilters,
    emptyCopy,
    filtered,
    counts,
    matchingTotal,
    grouped,
    dayKeys,
    countsByDay,
    hasActiveFilters,
    resultsLabel,
    activeFilterCount,
  };
}
