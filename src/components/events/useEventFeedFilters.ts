"use client";

import { useMemo } from "react";
import type { CampusEvent, EventCategory } from "@/types/event";
import { groupByDay } from "@/lib/event-grouping";
import {
  CATEGORIES,
  matchesCategory,
  matchesDayWindow,
  type CategoryValue,
  type DayWindow,
} from "./events-filters";

function buildEventSearchText(event: CampusEvent) {
  return [event.title, event.description, event.host, event.location, ...event.tags]
    .join(" ")
    .toLowerCase();
}

type UseEventFeedFiltersArgs = {
  loadedEvents: CampusEvent[];
  category: CategoryValue;
  query: string;
  dayWindow: DayWindow;
  todayKey: string;
};

export function useEventFeedFilters({
  loadedEvents,
  category,
  query,
  dayWindow,
  todayKey,
}: UseEventFeedFiltersArgs) {
  const trimmedQuery = query.trim();
  const normalizedQuery = trimmedQuery.toLowerCase();

  const eventSearchText = useMemo(
    () => loadedEvents.map(buildEventSearchText),
    [loadedEvents]
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

  const filtered = useMemo(() => {
    return filteredExceptCategory.filter((ev) => matchesCategory(ev, category));
  }, [filteredExceptCategory, category]);

  const counts = useMemo(() => {
    const map = new Map<CategoryValue, number>();
    map.set("all", filteredExceptCategory.length);
    for (const c of CATEGORIES) {
      if (c.value === "all") continue;
      map.set(
        c.value,
        filteredExceptCategory.filter((ev) => matchesCategory(ev, c.value)).length
      );
    }
    return map;
  }, [filteredExceptCategory]);

  const grouped = useMemo(() => groupByDay(filtered), [filtered]);
  const dayKeys = Array.from(grouped.keys());

  const categoriesByDay = useMemo(() => {
    const map = new Map<string, EventCategory[]>();
    for (const [key, evs] of grouped) {
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
  }, [grouped]);

  const hasActiveFilters =
    category !== "all" || trimmedQuery.length > 0 || dayWindow !== "all";

  const resultsLabel = hasActiveFilters
    ? `${filtered.length} matching ${filtered.length === 1 ? "event" : "events"}`
    : `${filtered.length} ${filtered.length === 1 ? "event" : "events"} loaded`;

  const activeFilterCount =
    (category !== "all" ? 1 : 0) + (dayWindow !== "all" ? 1 : 0);

  return {
    trimmedQuery,
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
