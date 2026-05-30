"use client";

import { useMemo } from "react";
import type { CampusEvent } from "@/types/event";
import type { EventFilterCountSource } from "@/types/events-feed";
import { getEmptyFeedCopy } from "@/lib/events/empty-feed-copy";
import { groupByDay } from "@/lib/events/grouping";
import {
  buildEventSearchText,
  countEventsByCategory,
  filterEventSource,
  normalizeEventQuery,
  type CategoryValue,
  type DayWindow,
} from "./events-filters";

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
  const normalizedQuery = normalizeEventQuery(trimmedQuery);
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
  const filters = useMemo(
    () => ({ category, dayWindow, todayKey, normalizedQuery }),
    [category, dayWindow, todayKey, normalizedQuery]
  );

  const filteredExceptCategory = useMemo(() => {
    return filterEventSource(loadedEvents, filters, {
      includeCategory: false,
      searchText: eventSearchText,
    });
  }, [loadedEvents, filters, eventSearchText]);

  const countSourceExceptCategory = useMemo(() => {
    return filterEventSource(filterCountSource, filters, {
      includeCategory: false,
      searchText: countSourceSearchText,
    });
  }, [filterCountSource, filters, countSourceSearchText]);

  const filteredCalendarEvents = useMemo(() => {
    return filterEventSource(calendarSourceEvents, filters, {
      searchText: calendarSearchText,
    });
  }, [calendarSourceEvents, filters, calendarSearchText]);

  const filtered = useMemo(() => {
    return filterEventSource(filteredExceptCategory, filters);
  }, [filteredExceptCategory, filters]);

  const counts = useMemo(() => {
    return countEventsByCategory(countSourceExceptCategory);
  }, [countSourceExceptCategory]);

  const grouped = useMemo(() => groupByDay(filtered), [filtered]);
  const calendarGrouped = useMemo(
    () => groupByDay(filteredCalendarEvents),
    [filteredCalendarEvents]
  );
  const dayKeys = Array.from(grouped.keys());

  // Per-day event count drives the calendar heat map. Real counts (not
  // distinct categories) so a day with five social events reads as busy.
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
  const matchingTotal = counts.get(category) ?? 0;
  const resultsLabel = hasActiveFilters
    ? `${matchingTotal} matching ${matchingTotal === 1 ? "event" : "events"}`
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
    matchingTotal,
    grouped,
    dayKeys,
    countsByDay,
    hasActiveFilters,
    resultsLabel,
    activeFilterCount,
  };
}
