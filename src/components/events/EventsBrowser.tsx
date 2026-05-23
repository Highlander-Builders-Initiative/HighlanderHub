"use client";

import {
  useState,
  useMemo,
  useEffect,
  useLayoutEffect,
  useRef,
  useCallback,
} from "react";
import type { CampusEvent } from "@/types/event";
import { EventsLeftRail } from "./EventsLeftRail";
import { EventsRightRail } from "./EventsRightRail";
import { EventsMobileFilterSheet } from "./EventsMobileFilterSheet";
import { EventsFeedColumn } from "./EventsFeedColumn";
import {
  pacificCalendarGridRange,
  pacificDayKey,
  pacificTodayKey,
  startOfPacificMonthKey,
} from "@/lib/dates";
import { track } from "@/lib/analytics";
import {
  clearEventFeedReturnState,
  getSavedEventFeedSnapshotForRestore,
  saveEventFeedSnapshot,
} from "@/lib/event-feed-session";
import { fetchCalendarEvents, fetchEventsPage } from "@/lib/events-api";
import { getSavedScrollPosition } from "@/lib/scroll-restoration";
import { restoreSavedEventFeedSpot } from "@/lib/event-feed-restore";
import {
  type CategoryValue,
  type DayWindow,
} from "./events-filters";
import { useEventFeedFilters } from "./useEventFeedFilters";
import { useInfiniteEventFeedLoader } from "./useInfiniteEventFeedLoader";
import { useObservedDayKey } from "./useObservedDayKey";

type EventsBrowserProps = {
  events: CampusEvent[];
  calendarEvents: CampusEvent[];
  summary: { total: number; upcomingThisWeek: number; freeFood: number };
  initialHasMore?: boolean;
  initialNextOffset?: number;
};

function calendarRangeKey(range: { start: string; end: string }) {
  return `${range.start}:${range.end}`;
}

function mergeEventsByStart(
  current: CampusEvent[],
  incoming: CampusEvent[]
): CampusEvent[] {
  const merged = new Map(current.map((event) => [event.id, event]));
  for (const event of incoming) {
    if (!merged.has(event.id)) merged.set(event.id, event);
  }
  return Array.from(merged.values()).sort(
    (a, b) => Date.parse(a.startsAt) - Date.parse(b.startsAt)
  );
}

export function EventsBrowser({
  events,
  calendarEvents: initialCalendarEvents,
  summary,
  initialHasMore = false,
  initialNextOffset = events.length,
}: EventsBrowserProps) {
  const [category, setCategory] = useState<CategoryValue>("all");
  const [query, setQuery] = useState("");
  const [dayWindow, setDayWindow] = useState<DayWindow>("all");
  const [loadedEvents, setLoadedEvents] = useState(events);
  const [hasMore, setHasMore] = useState(initialHasMore);
  const [nextOffset, setNextOffset] = useState(initialNextOffset);
  const [calendarEvents, setCalendarEvents] = useState(initialCalendarEvents);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [isRestoring, setIsRestoring] = useState(false);
  const [mobileSheetOpen, setMobileSheetOpen] = useState(false);

  const todayKey = useMemo(() => pacificTodayKey(), []);
  const [calendarCursor, setCalendarCursor] = useState<string>(() =>
    startOfPacificMonthKey(todayKey)
  );
  const calendarRange = useMemo(
    () => pacificCalendarGridRange(calendarCursor),
    [calendarCursor]
  );

  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const dayHeaderRefs = useRef<Map<string, HTMLElement>>(new Map());
  const userInitiatedScrollRef = useRef(0);
  const loadedCalendarRangeKey = useRef(calendarRangeKey(calendarRange));
  const restoreTarget = useRef<
    ReturnType<typeof getSavedEventFeedSnapshotForRestore>
  >(null);
  const returnScrollTarget = useRef<ReturnType<typeof getSavedScrollPosition>>(null);
  const isRestoringSpot = useRef(false);

  useEffect(() => {
    setLoadedEvents(events);
    setHasMore(initialHasMore);
    setNextOffset(initialNextOffset);
  }, [events, initialHasMore, initialNextOffset]);

  useEffect(() => {
    setCalendarEvents(initialCalendarEvents);
  }, [initialCalendarEvents]);

  useEffect(() => {
    const key = calendarRangeKey(calendarRange);
    if (key === loadedCalendarRangeKey.current) return;

    let cancelled = false;
    fetchCalendarEvents(calendarRange.start, calendarRange.end)
      .then((nextEvents) => {
        if (cancelled) return;
        loadedCalendarRangeKey.current = key;
        setCalendarEvents(nextEvents);
      })
      .catch(() => {
        if (cancelled) return;
        setCalendarEvents([]);
      });

    return () => {
      cancelled = true;
    };
  }, [calendarRange]);

  useEffect(() => {
    restoreTarget.current = getSavedEventFeedSnapshotForRestore();
    returnScrollTarget.current = getSavedScrollPosition();
  }, []);

  useEffect(() => {
    if (isRestoringSpot.current) return;
    saveEventFeedSnapshot({
      path: `${window.location.pathname}${window.location.search}`,
      scrollY: window.scrollY,
      events: loadedEvents,
      hasMore,
      nextOffset,
      category,
      query,
      dayWindow,
      loadedCount: loadedEvents.length,
    });
  }, [loadedEvents, hasMore, nextOffset, category, query, dayWindow]);

  const clearRestorationState = useCallback(() => {
    clearEventFeedReturnState();
    restoreTarget.current = null;
    returnScrollTarget.current = null;
  }, []);

  const {
    trimmedQuery,
    filtered,
    counts,
    grouped,
    dayKeys,
    categoriesByDay,
    hasActiveFilters,
    resultsLabel,
    activeFilterCount,
  } = useEventFeedFilters({
    loadedEvents,
    calendarEvents,
    category,
    query,
    dayWindow,
    todayKey,
  });

  const lastTrackedQuery = useRef("");
  useEffect(() => {
    if (trimmedQuery === lastTrackedQuery.current) return;
    const t = setTimeout(() => {
      if (trimmedQuery.length === 0) {
        lastTrackedQuery.current = "";
        return;
      }
      track("events_search", { query_length: trimmedQuery.length });
      lastTrackedQuery.current = trimmedQuery;
    }, 600);
    return () => clearTimeout(t);
  }, [trimmedQuery]);

  const clearFilters = useCallback(() => {
    setCategory("all");
    setQuery("");
    setDayWindow("all");
    track("events_clear_filters", {});
  }, []);

  const closeMobileSheet = useCallback(() => {
    setMobileSheetOpen(false);
  }, []);

  const handleCategory = useCallback((next: CategoryValue) => {
    setCategory(next);
    track("events_filter", { category: next });
  }, []);

  const handleDayWindow = useCallback((next: DayWindow) => {
    setDayWindow(next);
    track("events_day_window", { window: next });
  }, []);

  const scrollToDay = useCallback((dayKey: string) => {
    const el = dayHeaderRefs.current.get(dayKey);
    if (el) {
      userInitiatedScrollRef.current = Date.now();
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, []);

  const handleCalendarSelect = useCallback((dayKey: string) => {
    setCalendarCursor(startOfPacificMonthKey(dayKey));
    const eventsForDay = calendarEvents.filter(
      (event) => pacificDayKey(event.startsAt) === dayKey
    );
    if (eventsForDay.length > 0) {
      setLoadedEvents((current) => mergeEventsByStart(current, eventsForDay));
      window.requestAnimationFrame(() => scrollToDay(dayKey));
    } else {
      scrollToDay(dayKey);
    }
    track("events_calendar_jump", { day: dayKey });
  }, [calendarEvents, scrollToDay]);

  const { observedDayKey, setObservedDayKey } = useObservedDayKey({
    dayHeaderRefs,
    dayKeys,
    userInitiatedScrollRef,
    initialDayKey: todayKey,
  });

  useEffect(() => {
    setCalendarCursor((prev) => {
      const next = startOfPacificMonthKey(observedDayKey);
      return prev === next ? prev : next;
    });
  }, [observedDayKey]);

  const loadMore = useCallback(async () => {
    if (isRestoringSpot.current || isLoadingMore || !hasMore) return;

    setIsLoadingMore(true);
    setLoadError("");

    try {
      const page = await fetchEventsPage(nextOffset);

      setLoadedEvents((current) => {
        const seen = new Set(current.map((event) => event.id));
        const nextEvents = page.events.filter((event) => !seen.has(event.id));
        return [...current, ...nextEvents];
      });
      setHasMore(page.hasMore);
      setNextOffset(page.nextOffset);
    } catch {
      setLoadError("Could not load more events. Try again.");
    } finally {
      setIsLoadingMore(false);
    }
  }, [hasMore, isLoadingMore, nextOffset]);

  const restoreSavedSpot = useCallback(async () => {
    const snapshot = restoreTarget.current;
    const returnScroll = returnScrollTarget.current;
    if (isRestoringSpot.current) return;

    const path = `${window.location.pathname}${window.location.search}`;
    if (!snapshot && !returnScroll) return;
    if (snapshot && snapshot.path !== path) return;
    if (!snapshot && returnScroll?.path !== path) return;

    isRestoringSpot.current = true;
    setIsRestoring(true);

    try {
      const restored = await restoreSavedEventFeedSpot({
        snapshot,
        returnScroll,
        path,
        currentEvents: loadedEvents,
        currentHasMore: hasMore,
        currentNextOffset: nextOffset,
        setCategory,
        setQuery,
        setDayWindow,
        setLoadedEvents,
        setHasMore,
        setNextOffset,
      });
      if (restored) {
        clearRestorationState();
      }
    } catch {
      restoreTarget.current = null;
      returnScrollTarget.current = null;
    } finally {
      isRestoringSpot.current = false;
      setIsRestoring(false);
    }
  }, [clearRestorationState, hasMore, loadedEvents, nextOffset]);

  useLayoutEffect(() => {
    void restoreSavedSpot();
  }, [restoreSavedSpot]);

  useInfiniteEventFeedLoader({
    loadMoreRef,
    hasMore,
    loadError,
    isLoadingMore,
    isRestoring,
    onLoadMore: loadMore,
  });

  const openMobileFilters = useCallback(() => {
    setMobileSheetOpen(true);
  }, []);

  return (
    <section id="events" className="mx-auto max-w-7xl px-4 pb-20 sm:px-6">
      <div className="lg:grid lg:grid-cols-[208px_minmax(0,1fr)_312px] lg:gap-10">
        <aside
          aria-label="Browse events"
          className="hidden lg:sticky lg:top-0 lg:block lg:max-h-screen lg:self-start lg:overflow-y-auto lg:py-8"
        >
          <EventsLeftRail
            category={category}
            onCategoryChange={handleCategory}
            counts={counts}
          />
        </aside>

        <EventsFeedColumn
          summary={summary}
          query={query}
          onQueryChange={setQuery}
          onOpenMobileFilters={openMobileFilters}
          activeFilterCount={activeFilterCount}
          resultsLabel={resultsLabel}
          hasActiveFilters={hasActiveFilters}
          onClearFilters={clearFilters}
          todayKey={todayKey}
          dayKeys={dayKeys}
          grouped={grouped}
          loadedCount={loadedEvents.length}
          loadMoreRef={loadMoreRef}
          hasMore={hasMore}
          loadError={loadError}
          isLoadingMore={isLoadingMore}
          onLoadMore={loadMore}
          dayHeaderRefs={dayHeaderRefs}
        />

        <aside
          aria-label="Calendar and time filter"
          className="hidden lg:sticky lg:top-0 lg:block lg:max-h-screen lg:self-start lg:overflow-y-auto lg:py-8"
        >
          <EventsRightRail
            cursor={calendarCursor}
            onCursorChange={setCalendarCursor}
            todayKey={todayKey}
            selectedKey={observedDayKey}
            onSelect={handleCalendarSelect}
            categoriesByDay={categoriesByDay}
            dayWindow={dayWindow}
            onDayWindowChange={handleDayWindow}
          />
        </aside>
      </div>

      <EventsMobileFilterSheet
        open={mobileSheetOpen}
        onClose={closeMobileSheet}
        category={category}
        onCategoryChange={handleCategory}
        counts={counts}
        dayWindow={dayWindow}
        onDayWindowChange={handleDayWindow}
        cursor={calendarCursor}
        onCursorChange={setCalendarCursor}
        todayKey={todayKey}
        selectedKey={observedDayKey}
        onSelect={(dayKey) => {
          setObservedDayKey(dayKey);
          handleCalendarSelect(dayKey);
          setMobileSheetOpen(false);
        }}
        categoriesByDay={categoriesByDay}
        onClear={clearFilters}
        hasActiveFilters={hasActiveFilters}
        resultCount={filtered.length}
      />
    </section>
  );
}
