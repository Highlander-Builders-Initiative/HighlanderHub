"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
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
import { SCROLL_SPY_OFFSET_PX } from "@/lib/events/observed-day-key";
import {
  eventFeedQueriesEqual,
  matchesEventFilters,
  type EventFeedQuery,
} from "./events-filters";
import { useInfiniteEventFeedLoader } from "./useInfiniteEventFeedLoader";
import { useObservedDayKey } from "./useObservedDayKey";

type UseEventFeedNavigationArgs = {
  active: boolean;
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
  feedFilters: EventFeedQuery;
  /** Filters the loaded pages were fetched with; offsets belong to them. */
  pageFilters: EventFeedQuery;
};

export function useEventFeedNavigation({
  active,
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
  pageFilters,
}: UseEventFeedNavigationArgs) {
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const dayHeaderRefs = useRef<Map<string, HTMLElement>>(new Map());
  const daySectionRefs = useRef<Map<string, HTMLElement>>(new Map());
  const userInitiatedScrollRef = useRef(0);
  const pendingCalendarScrollRef = useRef<string | null>(null);
  // Re-runs the jump effect on every click; a day that is already loaded
  // changes none of its other dependencies.
  const [calendarJumpCount, setCalendarJumpCount] = useState(0);
  const calendarJumpSuppressUntilRef = useRef(0);
  const pendingLoadAnchorRef = useRef<{
    dayKey: string;
    top: number;
  } | null>(null);

  const { observedDayKey, setObservedDayKey, pastFirstDayHeading } = useObservedDayKey({
    dayHeaderRefs,
    daySectionRefs,
    dayKeys,
    userInitiatedScrollRef,
    initialDayKey: todayKey,
  });

  const mergeCalendarEventsForDay = useCallback(
    (dayKey: string) => {
      // An empty (or filtered-out) target has nowhere to scroll. Do not
      // expand the feed with earlier dates just because they precede it.
      const hasTarget = calendarEvents.some(
        (event) =>
          pacificDayKey(event.startsAt) === dayKey &&
          matchesEventFilters(event, { ...feedFilters, todayKey })
      );
      if (!hasTarget) return false;

      const lastLoadedDay = dayKeys.at(-1) ?? "";
      const eventsToMerge =
        dayKey > lastLoadedDay
          ? calendarEvents.filter((event) => {
              const key = pacificDayKey(event.startsAt);
              // The final page can end partway through this day.
              return key >= lastLoadedDay && key <= dayKey;
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
    [calendarEvents, dayKeys, feedFilters, loadedEvents, setLoadedEvents, todayKey]
  );

  const handleCalendarSelect = useCallback(
    (dayKey: string) => {
      const now = Date.now();
      pendingCalendarScrollRef.current = dayKey;
      setCalendarJumpCount((count) => count + 1);
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
    if (!active) {
      pendingCalendarScrollRef.current = null;
      return;
    }
    const pending = pendingCalendarScrollRef.current;
    if (!pending) return;

    const el = daySectionRefs.current.get(pending);
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

    // A mobile heading is sticky: its viewport position is not the start of
    // the day. Measure the section plus its heading inset instead.
    const targetTop = () => {
      const headingInset = el.clientTop + parseFloat(getComputedStyle(el).paddingTop);
      const top = window.scrollY + el.getBoundingClientRect().top + headingInset - SCROLL_SPY_OFFSET_PX;
      return Math.max(0, Math.min(top, document.documentElement.scrollHeight - window.innerHeight));
    };
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: targetTop(), behavior: reduced ? "instant" : "smooth" });

    let rafId = 0;
    let previousY = window.scrollY;
    let stableFrames = 0;
    const inputs = ["wheel", "touchstart", "pointerdown", "keydown"] as const;
    const cleanup = () => {
      cancelAnimationFrame(rafId);
      for (const input of inputs) window.removeEventListener(input, cancel);
    };
    const cancel = () => {
      // Stop the browser's animation too, so the user's scroll takes over.
      window.scrollTo({ top: window.scrollY, behavior: "instant" });
      pendingCalendarScrollRef.current = null;
      calendarJumpSuppressUntilRef.current = 0;
      userInitiatedScrollRef.current = 0;
      cleanup();
    };
    const settle = () => {
      userInitiatedScrollRef.current = Date.now();
      const y = window.scrollY;
      stableFrames = Math.abs(y - previousY) < 1 ? stableFrames + 1 : 0;
      previousY = y;
      if (stableFrames >= 3) {
        // content-visibility replaces estimated card heights as we scroll.
        // Correct after the smooth scroll stops, then verify the new layout
        // also settles. Only do this while the user still wants this jump.
        const top = targetTop();
        if (Math.abs(top - y) <= 1) {
          pendingCalendarScrollRef.current = null;
          cleanup();
          return;
        }
        window.scrollTo({ top, behavior: "instant" });
        stableFrames = 0;
      }
      rafId = requestAnimationFrame(settle);
    };
    for (const input of inputs) window.addEventListener(input, cancel, { passive: true });
    rafId = requestAnimationFrame(settle);

    return cleanup;
  }, [
    active,
    calendarJumpCount,
    dayKeys,
    isCalendarLoading,
    isLoadingMore,
    mergeCalendarEventsForDay,
    setObservedDayKey,
  ]);

  useLayoutEffect(() => {
    const anchor = pendingLoadAnchorRef.current;
    pendingLoadAnchorRef.current = null;
    // A page that was already in flight must not override a calendar jump.
    if (!anchor || pendingCalendarScrollRef.current) return;

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

  // Offsets belong to the loaded list's query. Wait until the selected
  // filters match that list, fetch with those filters, and drop a response
  // if the list was replaced while the request was in flight.
  const pageFiltersRef = useRef(pageFilters);
  useLayoutEffect(() => {
    pageFiltersRef.current = pageFilters;
  }, [pageFilters]);
  const filtersReady = eventFeedQueriesEqual(feedFilters, pageFilters);

  const loadMore = useCallback(async () => {
    if (!active || isRestoring || isLoadingMore || !hasMore || !filtersReady) {
      return;
    }
    if (
      pendingCalendarScrollRef.current ||
      Date.now() < calendarJumpSuppressUntilRef.current
    ) {
      return;
    }

    setIsLoadingMore(true);
    setLoadError("");

    const requested = pageFilters;
    try {
      const page = await fetchEventsPage(nextOffset, undefined, requested);
      if (!eventFeedQueriesEqual(pageFiltersRef.current, requested)) return;
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
    active,
    hasMore,
    isLoadingMore,
    isRestoring,
    nextOffset,
    observedDayKey,
    pageFilters,
    filtersReady,
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
    isRestoring: isRestoring || !active || !filtersReady,
    onLoadMore: loadMore,
    suppressAutoLoadUntilRef: calendarJumpSuppressUntilRef,
    pendingCalendarScrollRef,
  });

  return {
    loadMoreRef,
    dayHeaderRefs,
    daySectionRefs,
    observedDayKey,
    pastFirstDayHeading,
    hideLoadMoreHint,
    handleCalendarSelect,
    loadMore,
  };
}
