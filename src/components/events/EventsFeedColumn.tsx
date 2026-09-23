"use client";

import {
  useEffect,
  useMemo,
  useState,
  type MutableRefObject,
  type RefObject,
} from "react";
import type { CampusEvent } from "@/types/event";
import type { Club } from "@/lib/clubs";
import { pacificDayHeading } from "@/lib/dates";
import type { EmptyFeedCopy } from "@/lib/events/empty-feed-copy";
import { EventCard, EventCompactRow } from "./EventCard";
import { ActiveFilterChips } from "./ActiveFilterChips";
import { EventFeedViewToggle } from "./EventFeedViewToggle";
import { EventSearchBox } from "./EventSearchBox";
import type { FeedView } from "./events-filters";
import type { EventFeedActiveFilters } from "./useEventFeedFilters";

type Props = {
  summary: { upcomingThisWeek: number };
  upcomingTotal: number;
  query: string;
  clubs: Club[];
  onQueryChange: (next: string) => void;
  onOpenMobileFilters: () => void;
  activeFilterCount: number;
  resultsLabel: string;
  activeFilters: EventFeedActiveFilters;
  emptyCopy: EmptyFeedCopy;
  hasActiveFilters: boolean;
  onClearFilters: () => void;
  onClearCategory: () => void;
  onClearDayWindow: () => void;
  onClearQuery: () => void;
  todayKey: string;
  /** The list's shape. Always "cards" below lg, where the toggle is hidden. */
  view: FeedView;
  onViewChange: (next: FeedView) => void;
  dayKeys: string[];
  grouped: Map<string, CampusEvent[]>;
  loadedCount: number;
  loadMoreRef: RefObject<HTMLDivElement>;
  hasMore: boolean;
  hideLoadMoreHint?: boolean;
  loadError: string;
  isLoadingMore: boolean;
  onLoadMore: () => void;
  dayHeaderRefs: MutableRefObject<Map<string, HTMLElement>>;
  daySectionRefs: MutableRefObject<Map<string, HTMLElement>>;
};

export function EventsFeedColumn({
  summary,
  upcomingTotal,
  query,
  clubs,
  onQueryChange,
  onOpenMobileFilters,
  activeFilterCount,
  resultsLabel,
  activeFilters,
  emptyCopy,
  hasActiveFilters,
  onClearFilters,
  onClearCategory,
  onClearDayWindow,
  onClearQuery,
  todayKey,
  view,
  onViewChange,
  dayKeys,
  grouped,
  loadedCount,
  loadMoreRef,
  hasMore,
  hideLoadMoreHint = false,
  loadError,
  isLoadingMore,
  onLoadMore,
  dayHeaderRefs,
  daySectionRefs,
}: Props) {
  const showEmptyState = dayKeys.length === 0;
  const [showBackToTop, setShowBackToTop] = useState(false);

  useEffect(() => {
    const onScroll = () => setShowBackToTop(window.scrollY > 480);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const scrollToTop = () => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
  };

  const daySections = useMemo(
    () =>
      dayKeys.map((day) => {
        const dayEvents = grouped.get(day)!;
        const heading = pacificDayHeading(day, todayKey);
        return { day, dayEvents, heading };
      }),
    [dayKeys, grouped, todayKey]
  );

  return (
    <div className="min-w-0 pt-6 sm:pt-8 lg:py-8">
      {/* The page title is the one brand moment in the feed (Bricolage);
          the day headings below carry the date, so the title doesn't. */}
      <header className="mb-7 flex items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="font-display text-[28px] font-semibold leading-[1.05] tracking-[-0.025em] text-ink sm:text-[34px]">
            Events
          </h1>
          <p className="mt-2 max-w-[58ch] text-[14px] text-muted">
            {summary.upcomingThisWeek} this week · {upcomingTotal} upcoming
          </p>
        </div>
        <EventFeedViewToggle
          view={view}
          onViewChange={onViewChange}
          className="hidden lg:flex"
        />
      </header>

      {/* Filter bar: a liquid-glass capsule. From lg it floats free over the
          feed; the rail calendar marks the day in view, so the bar carries no
          date of its own. On phones it sits in a frosted strip that runs on
          into the sticky day heading below (top: 56 = the strip's pt-2 +
          h-12), so the feed never shows between the two. */}
      <div className="sticky top-0 z-20 -mx-4 mb-5 bg-surface/80 px-4 py-2 backdrop-blur-xl sm:-mx-6 sm:px-6 lg:top-3 lg:mx-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none">
        <div className="liquid-glass relative flex h-12 items-center gap-2 rounded-full p-1.5 lg:gap-3 lg:pl-4">
          <button
            type="button"
            onClick={onOpenMobileFilters}
            className="interactive-focus relative inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full bg-ink/[0.06] px-3.5 text-[13px] font-medium text-ink transition-colors hover:bg-ink/10 lg:hidden"
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
                className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-ink px-1 text-[10px] text-canvas"
              >
                {activeFilterCount}
              </span>
            )}
          </button>

          <EventSearchBox query={query} clubs={clubs} onQueryChange={onQueryChange} />

          {/* Back to top: grows in at the capsule's end once past the fold. */}
          <button
            type="button"
            onClick={scrollToTop}
            aria-label="Back to top"
            aria-hidden={!showBackToTop}
            tabIndex={showBackToTop ? 0 : -1}
            className={`interactive-focus inline-flex h-9 shrink-0 items-center justify-center overflow-hidden rounded-full bg-ink/[0.06] text-ink transition-[width,opacity,transform] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-ink/10 motion-reduce:transition-none ${
              showBackToTop
                ? "w-9 opacity-100"
                : "pointer-events-none w-0 scale-75 opacity-0"
            }`}
          >
            <svg
              aria-hidden
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4 shrink-0"
            >
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </button>
        </div>
      </div>

      <ActiveFilterChips
        activeFilters={activeFilters}
        onClearCategory={onClearCategory}
        onClearDayWindow={onClearDayWindow}
        onClearQuery={onClearQuery}
        onClearAll={onClearFilters}
      />

      {/* The count shows only as a filter result ("12 matching events").
          Unfiltered it is a loading status, so it stays for screen readers. */}
      <p
        id="event-filter-summary"
        className={hasActiveFilters ? "mb-6 text-sm text-muted" : "sr-only"}
        aria-live="polite"
        aria-atomic="true"
      >
        {resultsLabel}
      </p>

      {showEmptyState && (
        <div className="py-14 sm:py-20">
          <p className="max-w-[42ch] text-2xl font-semibold leading-[1.2] tracking-[-0.015em] text-ink sm:text-[28px]">
            {emptyCopy.headline}
          </p>
          <p className="mt-3 max-w-[52ch] text-[15px] leading-[1.55] text-ink/70">
            {emptyCopy.nudge}
          </p>
          {hasActiveFilters && (
            <div className="mt-7">
              <button
                type="button"
                onClick={onClearFilters}
                className="interactive-focus inline-flex min-h-11 items-center rounded-lg bg-ink px-5 py-2 font-medium text-canvas transition-opacity hover:opacity-85"
              >
                Clear filters
              </button>
            </div>
          )}
        </div>
      )}

      {/* Day sections get their own wrapper so `first:` matches the first
          day. As siblings of the header, bar and chips it never did, and the
          first day kept a top rule under the search bar. */}
      <div>
        {daySections.map(({ day, dayEvents, heading }) => (
          <div
            key={day}
            ref={(el) => {
              if (el) daySectionRefs.current.set(day, el);
              else daySectionRefs.current.delete(day);
            }}
            className="mb-10 lg:border-t lg:border-ink/15 lg:pt-7 lg:first:border-t-0 lg:first:pt-0"
          >
            <h3
              ref={(el) => {
                if (el) dayHeaderRefs.current.set(day, el);
                else dayHeaderRefs.current.delete(day);
              }}
              data-day-key={day}
              className="sticky z-10 -mx-4 mb-3 flex scroll-mt-24 items-baseline gap-1.5 bg-surface/80 px-4 py-2 text-xl font-semibold tracking-[-0.01em] text-ink backdrop-blur-xl after:absolute after:inset-x-4 after:bottom-0 after:border-t after:border-ink/10 sm:-mx-6 sm:px-6 sm:after:inset-x-6 lg:static lg:mx-0 lg:mb-4 lg:bg-transparent lg:px-0 lg:py-0 lg:text-lg lg:backdrop-blur-none lg:after:hidden"
              style={{ top: 56 }}
            >
              {heading.label}{" "}
              <span className="font-medium text-faint">{heading.weekday}</span>
            </h3>
            {view === "compact" ? (
              // One surface per day, rows divided by hairlines (borders, so
              // dark mode's edge curve applies).
              <div className="divide-y divide-ink/[0.06] rounded-[20px] border border-ink/[0.06] bg-canvas">
                {dayEvents.map((ev) => (
                  <EventCompactRow key={ev.id} event={ev} loadedCount={loadedCount} />
                ))}
              </div>
            ) : (
              <div className="flex flex-col gap-5 sm:gap-2.5">
                {dayEvents.map((ev) => (
                  <EventCard key={ev.id} event={ev} loadedCount={loadedCount} />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {(hasMore || loadError || isLoadingMore) && (
        <div ref={loadMoreRef} className="mt-2 flex min-h-14 flex-col items-center gap-3">
          {loadError && (
            <p className="text-sm text-coral" role="status">
              {loadError}
            </p>
          )}
          {loadError && hasMore ? (
            <button
              type="button"
              onClick={onLoadMore}
              disabled={isLoadingMore}
              className="interactive-focus inline-flex min-h-11 items-center rounded-lg border border-ink/15 bg-canvas px-5 py-2 text-sm font-medium text-ink transition-colors hover:border-ink disabled:cursor-not-allowed disabled:opacity-50"
            >
              Retry
            </button>
          ) : (
            (isLoadingMore || (hasMore && !hideLoadMoreHint)) && (
              <p className="text-sm text-muted" role="status">
                {isLoadingMore ? "Loading" : "More below"}
              </p>
            )
          )}
        </div>
      )}
    </div>
  );
}
