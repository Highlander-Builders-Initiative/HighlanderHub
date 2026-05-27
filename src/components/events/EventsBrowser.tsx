"use client";

import {
  useState,
  useMemo,
  useEffect,
  useLayoutEffect,
  useRef,
  useCallback,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import type { CampusEvent } from "@/types/event";
import type { EventFilterCountSource } from "@/types/events-feed";
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
import { saveEventFeedSnapshot } from "@/lib/events/feed-session";
import { fetchEventsPage } from "@/lib/events/api";
import { calendarJumpEndsAtLoadedBoundary } from "@/lib/events/calendar-feed-pagination";
import { mergeUniqueEventsByStart } from "@/lib/events/merge";
import {
  type CategoryValue,
  type DayWindow,
} from "./events-filters";
import { useCalendarMonthEvents } from "./useCalendarMonthEvents";
import { useEventFeedFilters } from "./useEventFeedFilters";
import { useInfiniteEventFeedLoader } from "./useInfiniteEventFeedLoader";
import { useEventFeedRestore } from "./useEventFeedRestore";
import { useObservedDayKey } from "./useObservedDayKey";
import type { EventFeedRestorePatch } from "@/lib/events/feed-restore";

export type EventsBrowserInitialFilters = {
  category: CategoryValue;
  query: string;
  dayWindow: DayWindow;
};

const DEFAULT_INITIAL_FILTERS: EventsBrowserInitialFilters = {
  category: "all",
  query: "",
  dayWindow: "all",
};

type EventsBrowserProps = {
  events: CampusEvent[];
  calendarEvents: CampusEvent[];
  filterCountSource: EventFilterCountSource[];
  summary: { upcomingThisWeek: number };
  initialHasMore?: boolean;
  initialNextOffset?: number;
  initialFilters?: EventsBrowserInitialFilters;
};

export function EventsBrowser({
  events,
  calendarEvents: initialCalendarEvents,
  filterCountSource,
  summary,
  initialHasMore = false,
  initialNextOffset = events.length,
  initialFilters = DEFAULT_INITIAL_FILTERS,
}: EventsBrowserProps) {
  const router = useRouter();
  const pathname = usePathname();

  const [category, setCategory] = useState<CategoryValue>(
    initialFilters.category
  );
  const [query, setQuery] = useState(initialFilters.query);
  const [dayWindow, setDayWindow] = useState<DayWindow>(
    initialFilters.dayWindow
  );
  const [loadedEvents, setLoadedEvents] = useState(events);
  const [hasMore, setHasMore] = useState(initialHasMore);
  const [nextOffset, setNextOffset] = useState(initialNextOffset);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [loadError, setLoadError] = useState("");
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
  const daySectionRefs = useRef<Map<string, HTMLElement>>(new Map());
  const userInitiatedScrollRef = useRef(0);
  const pendingCalendarScrollRef = useRef<string | null>(null);
  const calendarJumpSuppressUntilRef = useRef(0);
  const pendingLoadAnchorRef = useRef<{
    dayKey: string;
    top: number;
  } | null>(null);

  useEffect(() => {
    setLoadedEvents(events);
    setHasMore(initialHasMore);
    setNextOffset(initialNextOffset);
  }, [events, initialHasMore, initialNextOffset]);

  const applyRestore = useCallback((patch: EventFeedRestorePatch) => {
    if (patch.category !== undefined) {
      setCategory(patch.category);
    }
    if (patch.query !== undefined) {
      setQuery(patch.query);
    }
    if (patch.dayWindow !== undefined) {
      setDayWindow(patch.dayWindow);
    }
    if (patch.loadedEvents !== undefined) {
      setLoadedEvents(patch.loadedEvents);
    }
    if (patch.hasMore !== undefined) {
      setHasMore(patch.hasMore);
    }
    if (patch.nextOffset !== undefined) {
      setNextOffset(patch.nextOffset);
    }
  }, []);

  const { calendarEvents, isCalendarLoading } = useCalendarMonthEvents({
    initialCalendarEvents,
    calendarRange,
  });

  const isRestoring = useEventFeedRestore({
    events,
    initialHasMore,
    initialNextOffset,
    applyRestore,
  });

  useEffect(() => {
    if (isRestoring) return;
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
  }, [loadedEvents, hasMore, nextOffset, category, query, dayWindow, isRestoring]);

  const {
    trimmedQuery,
    activeFilters,
    emptyCopy,
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
    filterCountSource,
    calendarEvents,
    category,
    query,
    dayWindow,
    todayKey,
  });

  // Mirror the active filter state to the URL via ?cat=&q=&when=. Uses
  // router.replace so each keystroke / chip click does not push a history
  // entry; deep links survive, the back button doesn't.
  const writeFiltersToUrl = useCallback(
    (next: {
      category: CategoryValue;
      query: string;
      dayWindow: DayWindow;
    }) => {
      const params = new URLSearchParams();
      if (next.category !== "all") params.set("cat", next.category);
      if (next.query) params.set("q", next.query);
      if (next.dayWindow !== "all") params.set("when", next.dayWindow);
      const search = params.toString();
      router.replace(search ? `${pathname}?${search}` : pathname, {
        scroll: false,
      });
    },
    [router, pathname]
  );

  // Category and day-window are discrete clicks; write the URL immediately so
  // a chip toggle is shareable the same frame it lands.
  useEffect(() => {
    if (isRestoring) return;
    writeFiltersToUrl({ category, query: trimmedQuery, dayWindow });
    // trimmedQuery is intentionally excluded: text input shares the 600ms
    // debouncer below, which writes the URL and fires analytics together.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, dayWindow, isRestoring, writeFiltersToUrl]);

  // Search input piggybacks on the existing 600ms debouncer that gates the
  // events_search analytics ping; one timer writes the URL and fires the ping
  // together, so we never thrash the address bar mid-keystroke.
  const lastTrackedQuery = useRef(initialFilters.query.trim());
  useEffect(() => {
    if (isRestoring) return;
    if (trimmedQuery === lastTrackedQuery.current) return;
    const t = setTimeout(() => {
      writeFiltersToUrl({ category, query: trimmedQuery, dayWindow });
      if (trimmedQuery.length > 0) {
        track("events_search", { query_length: trimmedQuery.length });
      }
      lastTrackedQuery.current = trimmedQuery;
    }, 600);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trimmedQuery, isRestoring, writeFiltersToUrl]);

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

  const clearCategory = useCallback(() => {
    handleCategory("all");
  }, [handleCategory]);

  const clearDayWindow = useCallback(() => {
    handleDayWindow("all");
  }, [handleDayWindow]);

  const clearQuery = useCallback(() => {
    setQuery("");
  }, []);

  const { observedDayKey, setObservedDayKey } = useObservedDayKey({
    dayHeaderRefs,
    daySectionRefs,
    dayKeys,
    userInitiatedScrollRef,
    initialDayKey: todayKey,
  });

  const mergeCalendarEventsForDay = useCallback(
    (dayKey: string) => {
      const lastLoadedDay = dayKeys.at(-1) ?? "";
      const eventsToMerge =
        dayKey > lastLoadedDay
          ? calendarEvents.filter((event) => {
              const key = pacificDayKey(event.startsAt);
              return key > lastLoadedDay && key <= dayKey;
            })
          : calendarEvents.filter(
              (event) => pacificDayKey(event.startsAt) === dayKey
            );
      const loadedIds = new Set(loadedEvents.map((event) => event.id));
      const hasNewEvents = eventsToMerge.some(
        (event) => !loadedIds.has(event.id)
      );

      if (!hasNewEvents) return false;

      setLoadedEvents((current) =>
        mergeUniqueEventsByStart(current, eventsToMerge)
      );
      return true;
    },
    [calendarEvents, dayKeys, loadedEvents]
  );

  const handleCalendarSelect = useCallback(
    (dayKey: string) => {
      const now = Date.now();
      pendingCalendarScrollRef.current = dayKey;
      calendarJumpSuppressUntilRef.current = now + 1200;
      userInitiatedScrollRef.current = now;
      setObservedDayKey(dayKey);
      setCalendarCursor(startOfPacificMonthKey(dayKey));
      mergeCalendarEventsForDay(dayKey);

      track("events_calendar_jump", { day: dayKey });
    },
    [mergeCalendarEventsForDay, setObservedDayKey]
  );

  useLayoutEffect(() => {
    const pending = pendingCalendarScrollRef.current;
    if (!pending) return;

    const el = dayHeaderRefs.current.get(pending);
    if (!el) {
      if (mergeCalendarEventsForDay(pending) || isCalendarLoading) {
        return;
      }
      if (!dayKeys.includes(pending)) {
        pendingCalendarScrollRef.current = null;
      }
      return;
    }

    userInitiatedScrollRef.current = Date.now();
    setObservedDayKey(pending);
    el.scrollIntoView({ behavior: "smooth", block: "start" });

    const dayKey = pending;
    const timeoutId = window.setTimeout(() => {
      if (pendingCalendarScrollRef.current === dayKey) {
        pendingCalendarScrollRef.current = null;
      }
    }, 1200);

    return () => window.clearTimeout(timeoutId);
  }, [
    dayKeys,
    isCalendarLoading,
    isLoadingMore,
    mergeCalendarEventsForDay,
    setObservedDayKey,
  ]);

  useLayoutEffect(() => {
    const anchor = pendingLoadAnchorRef.current;
    if (!anchor) return;
    pendingLoadAnchorRef.current = null;

    const el = dayHeaderRefs.current.get(anchor.dayKey);
    if (!el) return;

    const delta = el.getBoundingClientRect().top - anchor.top;
    if (Math.abs(delta) < 1) return;

    userInitiatedScrollRef.current = Date.now();
    const root = document.scrollingElement ?? document.documentElement;
    root.scrollTop += delta;
  }, [loadedEvents]);

  useEffect(() => {
    if (pendingCalendarScrollRef.current) return;
    setCalendarCursor((prev) => {
      const next = startOfPacificMonthKey(observedDayKey);
      return prev === next ? prev : next;
    });
  }, [observedDayKey]);

  const hideLoadMoreHint = useMemo(
    () =>
      calendarJumpEndsAtLoadedBoundary(
        loadedEvents,
        calendarEvents,
        observedDayKey
      ),
    [loadedEvents, calendarEvents, observedDayKey]
  );

  const loadMore = useCallback(async () => {
    if (isRestoring || isLoadingMore || !hasMore) return;
    if (
      pendingCalendarScrollRef.current ||
      Date.now() < calendarJumpSuppressUntilRef.current
    ) {
      return;
    }

    setIsLoadingMore(true);
    setLoadError("");

    try {
      const page = await fetchEventsPage(nextOffset);
      const anchorEl = dayHeaderRefs.current.get(observedDayKey);
      if (anchorEl) {
        pendingLoadAnchorRef.current = {
          dayKey: observedDayKey,
          top: anchorEl.getBoundingClientRect().top,
        };
      }

      setLoadedEvents((current) => {
        return mergeUniqueEventsByStart(current, page.events);
      });
      setHasMore(page.hasMore);
      setNextOffset(page.nextOffset);
    } catch {
      setLoadError("Could not load more events. Try again.");
    } finally {
      setIsLoadingMore(false);
    }
  }, [hasMore, isLoadingMore, nextOffset, observedDayKey, isRestoring]);

  useInfiniteEventFeedLoader({
    loadMoreRef,
    hasMore,
    loadError,
    isLoadingMore,
    isRestoring,
    onLoadMore: loadMore,
    suppressAutoLoadUntilRef: calendarJumpSuppressUntilRef,
    pendingCalendarScrollRef,
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
          upcomingTotal={filterCountSource.length}
          query={query}
          onQueryChange={setQuery}
          onOpenMobileFilters={openMobileFilters}
          activeFilterCount={activeFilterCount}
          resultsLabel={resultsLabel}
          activeFilters={activeFilters}
          emptyCopy={emptyCopy}
          hasActiveFilters={hasActiveFilters}
          onClearFilters={clearFilters}
          onClearCategory={clearCategory}
          onClearDayWindow={clearDayWindow}
          onClearQuery={clearQuery}
          todayKey={todayKey}
          dayKeys={dayKeys}
          grouped={grouped}
          loadedCount={loadedEvents.length}
          loadMoreRef={loadMoreRef}
          hasMore={hasMore}
          hideLoadMoreHint={hideLoadMoreHint}
          loadError={loadError}
          isLoadingMore={isLoadingMore}
          onLoadMore={loadMore}
          dayHeaderRefs={dayHeaderRefs}
          daySectionRefs={daySectionRefs}
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
            isLoading={isCalendarLoading}
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
          handleCalendarSelect(dayKey);
          setMobileSheetOpen(false);
        }}
        categoriesByDay={categoriesByDay}
        isLoading={isCalendarLoading}
        onClear={clearFilters}
        hasActiveFilters={hasActiveFilters}
        resultCount={filtered.length}
      />
    </section>
  );
}
