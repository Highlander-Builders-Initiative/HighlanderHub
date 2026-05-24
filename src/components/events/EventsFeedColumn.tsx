"use client";

import { useMemo, type MutableRefObject, type RefObject } from "react";
import type { CampusEvent } from "@/types/event";
import { formatPacificDayKey } from "@/lib/dates";
import type { EmptyFeedCopy } from "@/lib/events/empty-feed-copy";
import { EventCard } from "./EventCard";
import { SubmitEventCta } from "./SubmitEventCta";
import { ActiveFilterChips } from "./ActiveFilterChips";
import type { EventFeedActiveFilters } from "./useEventFeedFilters";

type Props = {
  summary: { upcomingThisWeek: number };
  upcomingTotal: number;
  query: string;
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

  const daySections = useMemo(
    () =>
      dayKeys.map((day) => {
        const dayEvents = grouped.get(day)!;
        const isToday = day === todayKey;
        return { day, dayEvents, isToday };
      }),
    [dayKeys, grouped, todayKey]
  );

  return (
    <div className="min-w-0 lg:py-8">
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between sm:gap-6">
        <div className="min-w-0">
          <h1 className="font-display text-3xl font-semibold leading-[1.05] tracking-[-0.03em] text-ink sm:text-4xl">
            Events
          </h1>
          <p className="mt-2 max-w-[58ch] text-[15px] text-ink/75">
            {formatPacificDayKey(todayKey)} · {upcomingTotal}{" "}
            {upcomingTotal === 1 ? "event" : "events"} queued this week
          </p>
        </div>
        <div className="shrink-0 self-start sm:self-end">
          <SubmitEventCta surface="events_header" />
        </div>
      </header>

      <div
        className="sticky z-20 -mx-4 mb-5 border-b border-white/50 bg-white/55 px-4 py-2 shadow-[0_12px_28px_rgba(15,17,21,0.06)] backdrop-blur-xl sm:-mx-6 sm:px-6 lg:-mx-0 lg:px-0 lg:shadow-none"
        style={{ top: 0 }}
      >
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenMobileFilters}
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
              onChange={(e) => onQueryChange(e.target.value)}
              placeholder="Search title, host, location"
              aria-describedby="event-filter-summary"
              className="interactive-focus w-full border-b border-ink/15 bg-transparent py-1.5 pl-7 text-sm placeholder:text-muted focus:border-ink"
            />
          </div>
        </div>
      </div>

      <ActiveFilterChips
        activeFilters={activeFilters}
        onClearCategory={onClearCategory}
        onClearDayWindow={onClearDayWindow}
        onClearQuery={onClearQuery}
        onClearAll={onClearFilters}
      />

      <div className="mb-6">
        <p
          id="event-filter-summary"
          className="text-sm text-muted"
          aria-live="polite"
          aria-atomic="true"
        >
          {resultsLabel}
        </p>
      </div>

      {showEmptyState && (
        <div className="py-14 sm:py-20">
          <p className="max-w-[42ch] font-display text-2xl font-semibold leading-[1.2] tracking-[-0.02em] text-ink sm:text-[28px]">
            {emptyCopy.headline}
          </p>
          <p className="mt-3 max-w-[52ch] text-[15px] leading-[1.55] text-ink/70">
            {emptyCopy.nudge}
          </p>
          <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
            {hasActiveFilters && (
              <button
                type="button"
                onClick={onClearFilters}
                className="interactive-focus inline-flex min-h-11 items-center rounded-lg bg-ink px-5 py-2 font-medium text-canvas transition-opacity hover:opacity-85"
              >
                Clear filters
              </button>
            )}
            <span className="text-ink/55">
              Running something not listed?{" "}
              <SubmitEventCta variant="link" surface="empty_state" />
            </span>
          </div>
        </div>
      )}

      {daySections.map(({ day, dayEvents, isToday }) => (
        <div
          key={day}
          ref={(el) => {
            if (el) daySectionRefs.current.set(day, el);
            else daySectionRefs.current.delete(day);
          }}
          className="mb-10"
        >
          <div
            ref={(el) => {
              if (el) dayHeaderRefs.current.set(day, el);
              else dayHeaderRefs.current.delete(day);
            }}
            data-day-key={day}
            className="mb-3 scroll-mt-16 flex items-baseline justify-between gap-4 border-b border-ink/10 pb-2"
          >
            <h3 className="flex items-baseline gap-2.5 font-display text-xl font-semibold tracking-[-0.02em] text-ink sm:text-2xl">
              {formatPacificDayKey(day)}
              {isToday && (
                <span className="font-body text-[12px] font-medium text-ink/55">
                  Today
                </span>
              )}
            </h3>
            <span className="text-[13px] text-muted">
              {dayEvents.length} {dayEvents.length === 1 ? "event" : "events"}
            </span>
          </div>
          <div className="flex flex-col gap-5 sm:gap-2.5">
            {dayEvents.map((ev) => (
              <EventCard key={ev.id} event={ev} loadedCount={loadedCount} />
            ))}
          </div>
        </div>
      ))}

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
