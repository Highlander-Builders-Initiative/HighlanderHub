"use client";

import { useMemo } from "react";
import { EventsLeftRail } from "./EventsLeftRail";
import { EventsRightRail } from "./EventsRightRail";
import { SubmitEventCta } from "./SubmitEventCta";
import { formatPacificDayKey, pacificTodayKey, startOfPacificMonthKey } from "@/lib/dates";
import type { CategoryValue } from "./events-filters";

/**
 * Route-level placeholder for /events. The page chrome that does not depend on
 * data — masthead, Topics rail, mini calendar, the day heading, the search bar,
 * the Submit CTA — renders for real and in its final position, so navigating to
 * /events never shows a layout that then rearranges itself. Only the feed
 * column's event rows are stubbed, because those are the part still in flight.
 *
 * Rails are inert (pointer-events-none) rather than absent: a control that
 * looks live but silently swallows a click is worse than one that is visibly
 * waiting. Bars are static — no pulse — matching the rest of the site.
 */

const noop = () => {};
const EMPTY_CATEGORY_COUNTS = new Map<CategoryValue, number>();
const EMPTY_DAY_COUNTS = new Map<string, number>();

function Bar({ className }: { className: string }) {
  return <span aria-hidden className={`block rounded-full bg-ink/10 ${className}`} />;
}

/** One stubbed feed row, matched to EventCard's geometry. */
function EventRowSkeleton({ width }: { width: string }) {
  return (
    <div
      aria-hidden
      className="flex min-h-[6rem] w-full min-w-0 overflow-hidden rounded-2xl border border-ink/10 bg-canvas shadow-card"
    >
      {/* Time column */}
      <div className="relative flex w-16 shrink-0 flex-col items-center justify-center gap-1.5 px-2 sm:w-[68px]">
        <span aria-hidden className="pointer-events-none absolute bottom-0 right-0 top-0 w-[2px] bg-ink/10" />
        <Bar className="h-4 w-9" />
        <Bar className="h-2 w-5" />
      </div>

      {/* Text block */}
      <div className="flex min-w-0 flex-1 flex-col justify-center gap-2 py-3 pl-4 pr-10 sm:py-3.5 sm:pl-5">
        <Bar className={`h-4 ${width}`} />
        <Bar className="h-3 w-1/3" />
        <Bar className="h-3 w-1/2" />
      </div>
    </div>
  );
}

const ROW_WIDTHS = ["w-3/4", "w-2/3", "w-5/6", "w-1/2"];

function DayGroupSkeleton({ rows }: { rows: number }) {
  return (
    <div className="mb-10 lg:border-t lg:border-ink/15 lg:pt-7 lg:first:border-t-0 lg:first:pt-0">
      <div className="mb-3 px-4 py-2 sm:px-6 lg:mb-4 lg:px-0 lg:py-0">
        <Bar className="h-5 w-40" />
      </div>
      <div className="flex flex-col gap-5 sm:gap-2.5">
        {Array.from({ length: rows }).map((_, i) => (
          <EventRowSkeleton key={i} width={ROW_WIDTHS[i % ROW_WIDTHS.length]} />
        ))}
      </div>
    </div>
  );
}

export function EventsBrowserSkeleton() {
  const todayKey = useMemo(() => pacificTodayKey(), []);
  const monthCursor = useMemo(() => startOfPacificMonthKey(todayKey), [todayKey]);

  return (
    <section id="events" className="mx-auto max-w-7xl px-4 pb-20 sm:px-6">
      <div className="lg:grid lg:grid-cols-[208px_minmax(0,1fr)_312px] lg:gap-10">
        <aside
          aria-label="Browse events"
          className="hidden lg:sticky lg:top-0 lg:block lg:max-h-screen lg:self-start lg:overflow-y-auto lg:py-8"
        >
          <div className="pointer-events-none">
            <EventsLeftRail
              category="all"
              onCategoryChange={noop}
              counts={EMPTY_CATEGORY_COUNTS}
              countsPending
            />
          </div>
        </aside>

        <div className="min-w-0 pt-6 sm:pt-8 lg:py-8" aria-busy="true">
          <header className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between sm:gap-6">
            <div className="min-w-0">
              <h1 className="font-display text-[28px] font-semibold leading-[1.05] tracking-[-0.025em] text-ink sm:text-[34px]">
                {formatPacificDayKey(todayKey)}
              </h1>
              <p className="mt-2 flex h-[21px] items-center">
                <Bar className="h-3 w-52" />
              </p>
            </div>
            <div className="shrink-0 self-start sm:self-end">
              <SubmitEventCta surface="events_header" />
            </div>
          </header>

          {/* Filter bar: same sticky shell as the live feed, controls inert. */}
          <div
            className="sticky z-20 -mx-4 mb-5 border-b border-white/50 bg-white/55 px-4 py-2 shadow-[0_12px_28px_rgba(15,17,21,0.06)] backdrop-blur-xl sm:-mx-6 sm:px-6 lg:-mx-0 lg:px-0 lg:shadow-none"
            style={{ top: 0 }}
          >
            <div className="pointer-events-none flex items-center gap-2 lg:gap-3">
              <span className="inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-md border border-ink/15 bg-canvas px-3 text-[13px] font-medium text-ink/50 lg:hidden">
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
              </span>

              <div className="relative min-w-0 flex-1">
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
                <div className="w-full border-b border-ink/15 py-1.5 pl-7 text-sm text-muted">
                  Search events, or pick a club
                </div>
              </div>
            </div>
          </div>

          <div className="mb-6">
            <p className="text-sm text-muted" role="status">
              Loading events…
            </p>
          </div>

          <DayGroupSkeleton rows={3} />
          <DayGroupSkeleton rows={2} />
        </div>

        <aside
          aria-label="Calendar and time filter"
          className="hidden lg:sticky lg:top-0 lg:block lg:max-h-screen lg:self-start lg:overflow-y-auto lg:py-8"
        >
          <div className="pointer-events-none">
            <EventsRightRail
              cursor={monthCursor}
              onCursorChange={noop}
              todayKey={todayKey}
              selectedKey={todayKey}
              onSelect={noop}
              countsByDay={EMPTY_DAY_COUNTS}
              isLoading
              dayWindow="all"
              onDayWindowChange={noop}
            />
          </div>
        </aside>
      </div>
    </section>
  );
}
