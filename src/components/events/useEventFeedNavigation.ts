"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  type Dispatch,
  type SetStateAction,
} from "react";
import type { CampusEvent } from "@/types/event";
import {
  pacificDayKey,
  startOfPacificMonthKey,
} from "@/lib/dates";
import { track } from "@/lib/analytics";
import { fetchEventsPage } from "@/lib/events/api";
import { calendarJumpEndsAtLoadedBoundary } from "@/lib/events/calendar-feed-pagination";
import { mergeUniqueEventsByStart } from "@/lib/events/merge";
import type { CategoryValue, DayWindow } from "./events-filters";
import { useInfiniteEventFeedLoader } from "./useInfiniteEventFeedLoader";
import { useObservedDayKey } from "./useObservedDayKey";

type UseEventFeedNavigationArgs = {
  loadedEvents: CampusEvent[];
  setLoadedEvents: Dispatch<SetStateAction<CampusEvent[]>>;
  calendarEvents: CampusEvent[];
  dayKeys: string[];
  todayKey: string;
  hasMore: boolean;
  setHasMore: Dispatch<SetStateAction<boolean>>;
  nextOffset: number;
  setNextOffset: Dispatch<SetStateAction<number>>;
  isLoadingMore: boolean;
  setIsLoadingMore: Dispatch<SetStateAction<boolean>>;
  loadError: string;
  setLoadError: Dispatch<SetStateAction<string>>;
  isRestoring: boolean;
  isCalendarLoading: boolean;
  setCalendarCursor: Dispatch<SetStateAction<string>>;
  feedFilters: {
    query: string;
    category: CategoryValue;
    dayWindow: DayWindow;
  };
};

export function useEventFeedNavigation({
  loadedEvents,
  setLoadedEvents,
  calendarEvents,
  dayKeys,
  todayKey,
  hasMore,
  setHasMore,
  nextOffset,
  setNextOffset,
  isLoadingMore,
  setIsLoadingMore,
  loadError,
  setLoadError,
  isRestoring,
  isCalendarLoading,
  setCalendarCursor,
  feedFilters,
}: UseEventFeedNavigationArgs) {
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
    [calendarEvents, dayKeys, loadedEvents, setLoadedEvents]
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
    [mergeCalendarEventsForDay, setCalendarCursor, setObservedDayKey]
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
  }, [observedDayKey, setCalendarCursor]);

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
      const page = await fetchEventsPage(nextOffset, undefined, feedFilters);
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
  }, [
    hasMore,
    isLoadingMore,
    isRestoring,
    nextOffset,
    observedDayKey,
    feedFilters,
    setHasMore,
    setIsLoadingMore,
    setLoadError,
    setLoadedEvents,
    setNextOffset,
  ]);

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

  return {
    loadMoreRef,
    dayHeaderRefs,
    daySectionRefs,
    observedDayKey,
    hideLoadMoreHint,
    handleCalendarSelect,
    loadMore,
  };
}
