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
import { CalendarView } from "./CalendarView";
import { SubmitEventCta } from "./SubmitEventCta";
import { formatPacificDayKey } from "@/lib/dates";
import { groupByDay } from "@/lib/event-grouping";
import { track } from "@/lib/analytics";
import {
  clearEventFeedReturnState,
  getSavedEventFeedSnapshotForRestore,
  saveEventFeedSnapshot,
} from "@/lib/event-feed-session";
import { getSavedScrollPosition } from "@/lib/scroll-restoration";

type ViewMode = "list" | "calendar";

const CATEGORIES: { value: EventCategory | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "club", label: "Clubs" },
  { value: "academic", label: "Academic" },
  { value: "social", label: "Social" },
  { value: "career", label: "Career" },
  { value: "sports", label: "Sports" },
  { value: "arts", label: "Arts" },
  { value: "community", label: "Community" },
  { value: "free_food", label: "Free Food" },
];

type EventsBrowserProps = {
  events: CampusEvent[];
  initialHasMore?: boolean;
  initialNextOffset?: number;
};

type EventsApiPage = {
  events: CampusEvent[];
  hasMore: boolean;
  nextOffset: number;
};

function buildEventSearchText(event: CampusEvent) {
  // Cache the lowercase search blob once per loaded batch so typing only does
  // substring checks instead of rebuilding the same long strings on every
  // keystroke.
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
  initialHasMore = false,
  initialNextOffset = events.length,
}: EventsBrowserProps) {
  const [view, setView] = useState<ViewMode>("list");
  const [category, setCategory] = useState<EventCategory | "all">("all");
  const [query, setQuery] = useState("");
  const [loadedEvents, setLoadedEvents] = useState(events);
  const [hasMore, setHasMore] = useState(initialHasMore);
  const [nextOffset, setNextOffset] = useState(initialNextOffset);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [isRestoring, setIsRestoring] = useState(false);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const restoreTarget = useRef<
    ReturnType<typeof getSavedEventFeedSnapshotForRestore>
  >(null);
  const returnScrollTarget = useRef<ReturnType<typeof getSavedScrollPosition>>(null);
  const isRestoringSpot = useRef(false);
  const trimmedQuery = query.trim();
  const normalizedQuery = trimmedQuery.toLowerCase();
  const hasActiveFilters = category !== "all" || trimmedQuery.length > 0;

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
      view,
      category,
      query,
      loadedCount: loadedEvents.length,
    });
  }, [loadedEvents, hasMore, nextOffset, view, category, query]);

  const clearRestorationState = useCallback(() => {
    clearEventFeedReturnState();
    restoreTarget.current = null;
    returnScrollTarget.current = null;
  }, []);

  const eventSearchText = useMemo(
    () => loadedEvents.map(buildEventSearchText),
    [loadedEvents]
  );

  const filtered = useMemo(() => {
    return loadedEvents.filter((ev, index) => {
      if (category === "free_food") {
        if (ev.category !== "free_food" && !ev.tags.includes("free food")) {
          return false;
        }
      } else if (category !== "all" && ev.category !== category) {
        return false;
      }
      if (normalizedQuery && !eventSearchText[index].includes(normalizedQuery)) {
        return false;
      }
      return true;
    });
  }, [loadedEvents, category, normalizedQuery, eventSearchText]);

  const grouped = useMemo(() => groupByDay(filtered), [filtered]);
  const dayKeys = Array.from(grouped.keys());
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

  const clearFilters = () => {
    setCategory("all");
    setQuery("");
    track("events_clear_filters", {});
  };

  const handleCategory = (next: EventCategory | "all") => {
    setCategory(next);
    track("events_filter", { category: next });
  };

  const handleView = (next: ViewMode) => {
    setView(next);
    track("events_view_toggle", { view: next });
  };

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

  const restoreSavedSpot = useCallback(async () => {
    const snapshot = restoreTarget.current;
    const returnScroll = returnScrollTarget.current;
    const path = currentPath();
    if (isRestoringSpot.current) return;
    if (!snapshot && !returnScroll) return;
    if (snapshot && snapshot.path !== path) return;
    if (!snapshot && returnScroll?.path !== path) return;

    isRestoringSpot.current = true;
    setIsRestoring(true);

    const root = document.documentElement;
    const previousScrollBehavior = root.style.scrollBehavior;
    root.style.scrollBehavior = "auto";

    try {
      if (snapshot) {
        setView(snapshot.view);
        setCategory(snapshot.category);
        setQuery(snapshot.query);
        setLoadedEvents(snapshot.events);
        setHasMore(snapshot.hasMore);
        setNextOffset(snapshot.nextOffset);
      }

      await new Promise((resolve) => requestAnimationFrame(resolve));

      if (snapshot?.eventId && returnScroll?.eventId === snapshot.eventId) {
        const restored = await restoreEventsUntilTarget(
          snapshot.events,
          snapshot.nextOffset,
          snapshot.hasMore,
          returnScroll
        );

        setLoadedEvents(restored.current);
        setHasMore(restored.more);
        setNextOffset(restored.next);

        await new Promise((resolve) => requestAnimationFrame(resolve));

        if (restoreToEventCard(returnScroll.eventId, returnScroll.eventTop)) {
          clearRestorationState();
        }
      } else if (snapshot?.eventId) {
        if (restoreToEventCard(snapshot.eventId, snapshot.eventTop)) {
          clearRestorationState();
        }
      } else if (returnScroll?.eventId) {
        const restored = await restoreEventsUntilTarget(
          loadedEvents,
          nextOffset,
          hasMore,
          returnScroll
        );

        setLoadedEvents(restored.current);
        setHasMore(restored.more);
        setNextOffset(restored.next);

        await new Promise((resolve) => requestAnimationFrame(resolve));

        if (restoreToEventCard(returnScroll.eventId, returnScroll.eventTop)) {
          clearRestorationState();
        }
      } else if (returnScroll) {
        const rootScroller = document.scrollingElement ?? document.documentElement;
        rootScroller.scrollTop = returnScroll.scrollY;
        clearRestorationState();
      }
    } catch {
      restoreTarget.current = null;
      returnScrollTarget.current = null;
    } finally {
      root.style.scrollBehavior = previousScrollBehavior;
      isRestoringSpot.current = false;
      setIsRestoring(false);
    }
  }, [clearRestorationState, hasMore, loadedEvents, nextOffset]);

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
      <div
        className="sticky z-20 -mx-4 mb-6 border-b border-white/50 bg-white/55 px-4 shadow-[0_16px_40px_rgba(15,17,21,0.08)] backdrop-blur-xl transition-[top] duration-200 ease-out sm:-mx-6 sm:px-6"
        style={{ top: 0 }}
      >
        <div className="flex items-center gap-3 pt-2">
          <div
            role="tablist"
            aria-label="Choose view"
            className="flex shrink-0 items-end gap-4"
          >
            <button
              type="button"
              role="tab"
              aria-selected={view === "list"}
              onClick={() => handleView("list")}
              className="interactive-focus tab"
            >
              List
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === "calendar"}
              onClick={() => handleView("calendar")}
              className="interactive-focus tab"
            >
              Calendar
            </button>
          </div>
          <div className="relative ml-auto min-w-0 flex-1 sm:flex-none sm:w-64">
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
              placeholder="Search"
              aria-describedby="event-filter-summary"
              className="interactive-focus w-full border-b border-ink/15 bg-transparent py-1.5 pl-7 text-sm placeholder:text-muted focus:border-ink"
            />
          </div>
        </div>

        <div
          className="flex flex-wrap items-center gap-1.5 py-2"
          aria-label="Filter events by category"
        >
          {CATEGORIES.map((c) => {
            const active = category === c.value;
            return (
              <button
                type="button"
                key={c.value}
                onClick={() => handleCategory(c.value)}
                aria-pressed={active}
                className={`interactive-focus inline-flex min-h-8 items-center rounded-full border px-3 py-1 text-[13px] transition-colors ${
                  active
                    ? "border-ink bg-ink text-white"
                    : "border-ink/15 bg-white/60 text-ink hover:border-ink hover:bg-white/85"
                }`}
              >
                {c.label}
              </button>
            );
          })}
          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="interactive-focus ml-auto text-[13px] font-medium text-ink underline-offset-4 hover:underline"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div
        id="event-filter-summary"
        className="mx-auto mb-6 max-w-2xl text-sm text-muted"
        aria-live="polite"
        aria-atomic="true"
      >
        {resultsLabel}
      </div>

      {view === "calendar" ? (
        <CalendarView events={filtered} />
      ) : (
        <div className="mx-auto max-w-2xl">
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
            return (
              <div key={day} className="mb-12">
                <div className="mb-4 flex items-baseline justify-between gap-4 border-b border-ink/10 pb-3">
                  <h3 className="font-display text-2xl font-semibold tracking-[-0.02em] text-ink">
                    {formatPacificDayKey(day)}
                  </h3>
                  <span className="text-sm text-muted">
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
      )}
    </section>
  );
}
