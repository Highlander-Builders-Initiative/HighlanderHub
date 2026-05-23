"use client";

import {
  useState,
  useMemo,
  useEffect,
  useLayoutEffect,
  useRef,
  useCallback,
} from "react";
import type { CampusEvent, EventCategory } from "@/types/event";
import { EventCard } from "./EventCard";
import { EventsLeftRail } from "./EventsLeftRail";
import { EventsRightRail } from "./EventsRightRail";
import { EventsMobileFilterSheet } from "./EventsMobileFilterSheet";
import { SubmitEventCta } from "./SubmitEventCta";
import {
  formatPacificDayKey,
  pacificDayKey,
  pacificTodayKey,
  startOfPacificMonthKey,
} from "@/lib/dates";
import { groupByDay } from "@/lib/event-grouping";
import { track } from "@/lib/analytics";
import {
  clearEventFeedReturnState,
  getSavedEventFeedSnapshotForRestore,
  saveEventFeedSnapshot,
} from "@/lib/event-feed-session";
import { getSavedScrollPosition } from "@/lib/scroll-restoration";
import {
  CATEGORIES,
  matchesCategory,
  matchesDayWindow,
  type CategoryValue,
  type DayWindow,
} from "./events-filters";

type EventsBrowserProps = {
  events: CampusEvent[];
  summary: { total: number; upcomingThisWeek: number; freeFood: number };
  initialHasMore?: boolean;
  initialNextOffset?: number;
};

type EventsApiPage = {
  events: CampusEvent[];
  hasMore: boolean;
  nextOffset: number;
};

type RestoreSnapshot = NonNullable<
  ReturnType<typeof getSavedEventFeedSnapshotForRestore>
>;
type ReturnScroll = NonNullable<ReturnType<typeof getSavedScrollPosition>>;

type RestoreEventSource =
  | {
      kind: "snapshot";
      events: CampusEvent[];
      hasMore: boolean;
      nextOffset: number;
    }
  | { kind: "current" };

type RestoreStep =
  | { kind: "apply-snapshot"; snapshot: RestoreSnapshot }
  | { kind: "wait-for-frame" }
  | {
      kind: "load-until-event";
      source: RestoreEventSource;
      returnScroll: ReturnScroll;
    }
  | { kind: "restore-event-card"; eventId: string; eventTop?: number }
  | { kind: "restore-scroll"; scrollY: number };

type RestorePlan = {
  steps: RestoreStep[];
};

type ActiveFilterState = {
  hasActiveFilters: boolean;
  activeFilterCount: number;
};

function buildEventSearchText(event: CampusEvent) {
  return [event.title, event.description, event.host, event.location, ...event.tags]
    .join(" ")
    .toLowerCase();
}

function currentPath() {
  return `${window.location.pathname}${window.location.search}`;
}

function restoreToEventCard(eventId: string, eventTop = 0) {
  const target = document.querySelector<HTMLElement>(
    `[data-event-id="${CSS.escape(eventId)}"]`
  );
  if (!target) return false;

  const root = document.scrollingElement ?? document.documentElement;
  root.scrollTop = window.scrollY + target.getBoundingClientRect().top - eventTop;
  return true;
}

function waitForFrame() {
  return new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
}

function snapshotRestoreSource(snapshot: RestoreSnapshot): RestoreEventSource {
  return {
    kind: "snapshot",
    events: snapshot.events,
    hasMore: snapshot.hasMore,
    nextOffset: snapshot.nextOffset,
  };
}

function buildRestorePlan(
  snapshot: RestoreSnapshot | null,
  returnScroll: ReturnScroll | null,
  path: string
): RestorePlan | null {
  if (!snapshot && !returnScroll) return null;
  if (snapshot && snapshot.path !== path) return null;
  if (!snapshot && returnScroll?.path !== path) return null;

  const steps: RestoreStep[] = [];

  if (snapshot) {
    steps.push({ kind: "apply-snapshot", snapshot });
  }
  steps.push({ kind: "wait-for-frame" });

  if (snapshot?.eventId) {
    if (returnScroll?.eventId === snapshot.eventId) {
      steps.push({
        kind: "load-until-event",
        source: snapshotRestoreSource(snapshot),
        returnScroll,
      });
      steps.push({ kind: "wait-for-frame" });
      steps.push({
        kind: "restore-event-card",
        eventId: returnScroll.eventId,
        eventTop: returnScroll.eventTop,
      });
    } else {
      steps.push({
        kind: "restore-event-card",
        eventId: snapshot.eventId,
        eventTop: snapshot.eventTop,
      });
    }
  } else if (returnScroll?.eventId) {
    steps.push({
      kind: "load-until-event",
      source: snapshot ? snapshotRestoreSource(snapshot) : { kind: "current" },
      returnScroll,
    });
    steps.push({ kind: "wait-for-frame" });
    steps.push({
      kind: "restore-event-card",
      eventId: returnScroll.eventId,
      eventTop: returnScroll.eventTop,
    });
  } else if (returnScroll) {
    steps.push({ kind: "restore-scroll", scrollY: returnScroll.scrollY });
  }

  return steps.length > 0 ? { steps } : null;
}

function getActiveFilterState(
  category: CategoryValue,
  searchQuery: string,
  dayWindow: DayWindow
): ActiveFilterState {
  const hasCategoryFilter = category !== "all";
  const hasSearchFilter = searchQuery.length > 0;
  const hasDayWindowFilter = dayWindow !== "all";

  return {
    hasActiveFilters:
      hasCategoryFilter || hasSearchFilter || hasDayWindowFilter,
    activeFilterCount:
      (hasCategoryFilter ? 1 : 0) +
      (hasSearchFilter ? 1 : 0) +
      (hasDayWindowFilter ? 1 : 0),
  };
}

async function restoreEventsUntilTarget(
  current: CampusEvent[],
  next: number,
  more: boolean,
  returnScroll: NonNullable<ReturnType<typeof getSavedScrollPosition>>
) {
  let restored = current;
  let restoredNext = next;
  let restoredMore = more;

  if (typeof returnScroll.loadedCount === "number") {
    const limitToFetch = Math.max(0, returnScroll.loadedCount - current.length);
    if (limitToFetch > 0) {
      const response = await fetch(
        `/api/events?offset=${next}&limit=${limitToFetch}`
      );
      if (!response.ok) throw new Error("Unable to load more events.");
      const page = (await response.json()) as EventsApiPage;
      const seen = new Set(restored.map((event) => event.id));
      const nextEvents = page.events.filter((event) => !seen.has(event.id));
      if (nextEvents.length === 0 && page.nextOffset === restoredNext) {
        return { current: restored, next: restoredNext, more: restoredMore };
      }
      restored = [...restored, ...nextEvents];
      restoredNext = page.nextOffset;
      restoredMore = page.hasMore;
    }
  }

  while (
    restoredMore &&
    !restored.some((event) => event.id === returnScroll.eventId)
  ) {
    const response = await fetch(`/api/events?offset=${restoredNext}`);
    if (!response.ok) throw new Error("Unable to load more events.");
    const page = (await response.json()) as EventsApiPage;
    const seen = new Set(restored.map((event) => event.id));
    const nextEvents = page.events.filter((event) => !seen.has(event.id));
    if (nextEvents.length === 0 && page.nextOffset === restoredNext) break;
    restored = [...restored, ...nextEvents];
    restoredNext = page.nextOffset;
    restoredMore = page.hasMore;
  }

  return { current: restored, next: restoredNext, more: restoredMore };
}

export function EventsBrowser({
  events,
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
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [isRestoring, setIsRestoring] = useState(false);
  const [mobileSheetOpen, setMobileSheetOpen] = useState(false);

  const todayKey = useMemo(() => pacificTodayKey(), []);
  const [calendarCursor, setCalendarCursor] = useState<string>(() =>
    startOfPacificMonthKey(todayKey)
  );
  const [observedDayKey, setObservedDayKey] = useState<string>(todayKey);

  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const dayHeaderRefs = useRef<Map<string, HTMLElement>>(new Map());
  const userInitiatedScrollRef = useRef(0);
  const restoreTarget = useRef<
    ReturnType<typeof getSavedEventFeedSnapshotForRestore>
  >(null);
  const returnScrollTarget = useRef<ReturnType<typeof getSavedScrollPosition>>(null);
  const isRestoringSpot = useRef(false);

  const trimmedQuery = query.trim();
  const normalizedQuery = trimmedQuery.toLowerCase();
  const { hasActiveFilters, activeFilterCount } = getActiveFilterState(
    category,
    trimmedQuery,
    dayWindow
  );

  useEffect(() => {
    setLoadedEvents(events);
    setHasMore(initialHasMore);
    setNextOffset(initialNextOffset);
  }, [events, initialHasMore, initialNextOffset]);

  useEffect(() => {
    restoreTarget.current = getSavedEventFeedSnapshotForRestore();
    returnScrollTarget.current = getSavedScrollPosition();
  }, []);

  useEffect(() => {
    if (isRestoringSpot.current) return;
    saveEventFeedSnapshot({
      path: currentPath(),
      scrollY: window.scrollY,
      events: loadedEvents,
      hasMore,
      nextOffset,
      view: "list",
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

  const eventSearchText = useMemo(
    () => loadedEvents.map(buildEventSearchText),
    [loadedEvents]
  );

  // Apply search + dayWindow, but NOT category — used to count per-category
  // matches in the left rail, so counts reflect "if I clicked this category,
  // how many events would I see given my other filters."
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

  const resultsLabel = hasActiveFilters
    ? `${filtered.length} matching ${filtered.length === 1 ? "event" : "events"}`
    : `${filtered.length} ${filtered.length === 1 ? "event" : "events"} loaded`;

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

  const handleCalendarSelect = useCallback((dayKey: string) => {
    setObservedDayKey(dayKey);
    setCalendarCursor(startOfPacificMonthKey(dayKey));
    const el = dayHeaderRefs.current.get(dayKey);
    if (el) {
      userInitiatedScrollRef.current = Date.now();
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    track("events_calendar_jump", { day: dayKey });
  }, []);

  // Scroll spy: as day headers cross into the top of the viewport, track
  // which day the user is reading so the mini calendar can mirror it.
  useEffect(() => {
    if (dayKeys.length === 0) return;
    if (typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        // Honor click-initiated scrolls; don't fight the user.
        if (Date.now() - userInitiatedScrollRef.current < 600) return;
        // Pick the entry closest to (and at or below) the rootMargin band.
        const candidates = entries
          .filter((e) => e.isIntersecting)
          .map((e) => ({
            key: (e.target as HTMLElement).dataset.dayKey ?? "",
            top: e.boundingClientRect.top,
          }))
          .filter((c) => c.key)
          .sort((a, b) => a.top - b.top);

        if (candidates.length === 0) return;
        const next = candidates[0].key;
        setObservedDayKey((prev) => (prev === next ? prev : next));
      },
      { rootMargin: "0px 0px -80% 0px", threshold: 0 }
    );

    for (const el of dayHeaderRefs.current.values()) {
      observer.observe(el);
    }

    return () => observer.disconnect();
  }, [dayKeys]);

  // Cursor follows the day the user is reading, so the calendar shows the
  // right month without manual nav.
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
      const response = await fetch(`/api/events?offset=${nextOffset}`);
      if (!response.ok) throw new Error("Unable to load more events.");
      const page = (await response.json()) as EventsApiPage;

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

  const executeRestorePlan = useCallback(
    async (plan: RestorePlan) => {
      for (const step of plan.steps) {
        switch (step.kind) {
          case "apply-snapshot":
            setCategory(step.snapshot.category);
            setQuery(step.snapshot.query);
            setDayWindow(step.snapshot.dayWindow);
            setLoadedEvents(step.snapshot.events);
            setHasMore(step.snapshot.hasMore);
            setNextOffset(step.snapshot.nextOffset);
            break;
          case "wait-for-frame":
            await waitForFrame();
            break;
          case "load-until-event": {
            const source =
              step.source.kind === "snapshot"
                ? step.source
                : { events: loadedEvents, hasMore, nextOffset };
            const restored = await restoreEventsUntilTarget(
              source.events,
              source.nextOffset,
              source.hasMore,
              step.returnScroll
            );

            setLoadedEvents(restored.current);
            setHasMore(restored.more);
            setNextOffset(restored.next);
            break;
          }
          case "restore-event-card":
            if (restoreToEventCard(step.eventId, step.eventTop)) {
              clearRestorationState();
            }
            break;
          case "restore-scroll": {
            const rootScroller =
              document.scrollingElement ?? document.documentElement;
            rootScroller.scrollTop = step.scrollY;
            clearRestorationState();
            break;
          }
        }
      }
    },
    [clearRestorationState, hasMore, loadedEvents, nextOffset]
  );

  const restoreSavedSpot = useCallback(async () => {
    const snapshot = restoreTarget.current;
    const returnScroll = returnScrollTarget.current;
    if (isRestoringSpot.current) return;

    const plan = buildRestorePlan(snapshot, returnScroll, currentPath());
    if (!plan) return;

    isRestoringSpot.current = true;
    setIsRestoring(true);

    const root = document.documentElement;
    const previousScrollBehavior = root.style.scrollBehavior;
    root.style.scrollBehavior = "auto";

    try {
      await executeRestorePlan(plan);
    } catch {
      restoreTarget.current = null;
      returnScrollTarget.current = null;
    } finally {
      root.style.scrollBehavior = previousScrollBehavior;
      isRestoringSpot.current = false;
      setIsRestoring(false);
    }
  }, [executeRestorePlan]);

  useLayoutEffect(() => {
    void restoreSavedSpot();
  }, [restoreSavedSpot]);

  useEffect(() => {
    if (!hasMore || loadError || isRestoring) return;

    const target = loadMoreRef.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          void loadMore();
        }
      },
      { rootMargin: "640px 0px" }
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMore, loadError, loadMore, isRestoring]);

  return (
    <section id="events" className="mx-auto max-w-7xl px-4 pb-20 sm:px-6">
      <div className="lg:grid lg:grid-cols-[208px_minmax(0,1fr)_312px] lg:gap-10">
        {/* Left rail (desktop only) */}
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

        {/* Center column */}
        <div className="min-w-0 lg:py-8">
          {/* Page header (in-column on desktop, full width on mobile) */}
          <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between sm:gap-6">
            <div className="min-w-0">
              <h1 className="font-display text-3xl font-semibold leading-[1.05] tracking-[-0.03em] text-ink sm:text-4xl">
                Events
              </h1>
              <p className="mt-2 max-w-[58ch] text-[15px] text-ink/75">
                {summary.total} campus gatherings, with{" "}
                {summary.upcomingThisWeek} happening this week and{" "}
                {summary.freeFood} serving free food.
              </p>
            </div>
            <div className="shrink-0 self-start sm:self-end">
              <SubmitEventCta surface="events_header" />
            </div>
          </header>

          {/* Sticky control bar: search + mobile filter trigger */}
          <div
            className="sticky z-20 -mx-4 mb-5 border-b border-white/50 bg-white/55 px-4 py-2 shadow-[0_12px_28px_rgba(15,17,21,0.06)] backdrop-blur-xl sm:-mx-6 sm:px-6 lg:-mx-0 lg:px-0 lg:shadow-none"
            style={{ top: 0 }}
          >
            <div className="flex items-center gap-2">
              {/* Mobile filter trigger */}
              <button
                type="button"
                onClick={() => setMobileSheetOpen(true)}
                className="interactive-focus relative inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-md border border-ink/15 bg-canvas px-3 text-[13px] font-medium text-ink transition-colors hover:border-ink lg:hidden"
                aria-haspopup="dialog"
              >
                <svg
                  aria-hidden
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <path d="M3 6h18M6 12h12M10 18h4" />
                </svg>
                Filter
                {activeFilterCount > 0 && (
                  <span
                    aria-hidden
                    className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-ink px-1 font-mono text-[10px] text-canvas"
                  >
                    {activeFilterCount}
                  </span>
                )}
              </button>

              <div className="relative min-w-0 flex-1">
                <label htmlFor="event-search" className="sr-only">
                  Search events
                </label>
                <svg
                  aria-hidden="true"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="pointer-events-none absolute left-0 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
                >
                  <circle cx="11" cy="11" r="7" />
                  <path d="m20 20-3.5-3.5" />
                </svg>
                <input
                  id="event-search"
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search title, host, location"
                  aria-describedby="event-filter-summary"
                  className="interactive-focus w-full border-b border-ink/15 bg-transparent py-1.5 pl-7 text-sm placeholder:text-muted focus:border-ink"
                />
              </div>
            </div>
          </div>

          <div className="mb-6 flex items-baseline justify-between gap-3">
            <p
              id="event-filter-summary"
              className="text-sm text-muted"
              aria-live="polite"
              aria-atomic="true"
            >
              {resultsLabel}
            </p>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="interactive-focus shrink-0 text-[13px] font-medium text-ink underline-offset-4 hover:underline"
              >
                Clear
              </button>
            )}
          </div>

          {dayKeys.length === 0 && (
            <div className="rounded-xl border border-dashed border-ink/15 px-6 py-20 text-center">
              <p className="font-display text-xl text-ink mb-1">No matches.</p>
              <p className="text-sm text-muted">
                Try a broader filter or clear your search.
              </p>
              <button
                type="button"
                onClick={clearFilters}
                className="interactive-focus mt-5 inline-flex min-h-11 items-center rounded-lg bg-ink px-5 py-2 text-sm font-medium text-white transition-opacity hover:opacity-85"
              >
                Clear filters
              </button>
              <p className="mt-6 text-sm text-muted">
                Running something not listed?{" "}
                <SubmitEventCta variant="link" surface="empty_state" />
              </p>
            </div>
          )}

          {dayKeys.map((day) => {
            const dayEvents = grouped.get(day)!;
            const isToday = day === todayKey;
            return (
              <div key={day} className="mb-10">
                <div
                  ref={(el) => {
                    if (el) dayHeaderRefs.current.set(day, el);
                    else dayHeaderRefs.current.delete(day);
                  }}
                  data-day-key={day}
                  className="mb-3 flex items-baseline justify-between gap-4 border-b border-ink/10 pb-2"
                >
                  <h3 className="flex items-baseline gap-2.5 font-display text-xl font-semibold tracking-[-0.02em] text-ink sm:text-2xl">
                    {formatPacificDayKey(day)}
                    {isToday && (
                      <span className="font-body text-[12px] font-medium uppercase tracking-[0.06em] text-ink/55">
                        Today
                      </span>
                    )}
                  </h3>
                  <span className="text-[13px] text-muted">
                    {dayEvents.length}{" "}
                    {dayEvents.length === 1 ? "event" : "events"}
                  </span>
                </div>
                <div className="flex flex-col gap-2.5">
                  {dayEvents.map((ev) => (
                    <EventCard
                      key={ev.id}
                      event={ev}
                      loadedCount={loadedEvents.length}
                    />
                  ))}
                </div>
              </div>
            );
          })}

          {(hasMore || loadError || isLoadingMore) && (
            <div
              ref={loadMoreRef}
              className="mt-2 flex min-h-14 flex-col items-center gap-3"
            >
              {loadError && (
                <p className="text-sm text-coral" role="status">
                  {loadError}
                </p>
              )}
              {loadError && hasMore ? (
                <button
                  type="button"
                  onClick={loadMore}
                  disabled={isLoadingMore}
                  className="interactive-focus inline-flex min-h-11 items-center rounded-lg border border-ink/15 bg-canvas px-5 py-2 text-sm font-medium text-ink transition-colors hover:border-ink disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Retry
                </button>
              ) : (
                <p className="text-sm text-muted" role="status">
                  {isLoadingMore ? "Loading..." : "Scroll for more events"}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Right rail (desktop only) */}
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
