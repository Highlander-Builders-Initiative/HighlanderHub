"use client";

import { useState, useMemo } from "react";
import type { CampusEvent, EventCategory } from "@/types/event";
import { EventCard } from "./EventCard";
import { CalendarView } from "./CalendarView";
import { formatDay } from "@/lib/dates";
import { groupByDay } from "@/lib/event-grouping";

type ViewMode = "list" | "calendar";

const CATEGORIES: { value: EventCategory | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "club", label: "Clubs" },
  { value: "academic", label: "Academic" },
  { value: "career", label: "Career" },
  { value: "sports", label: "Sports" },
  { value: "arts", label: "Arts" },
  { value: "community", label: "Community" },
  { value: "free_food", label: "Free Food" },
];

export function EventsBrowser({ events }: { events: CampusEvent[] }) {
  const [view, setView] = useState<ViewMode>("list");
  const [category, setCategory] = useState<EventCategory | "all">("all");
  const [query, setQuery] = useState("");
  const [freeFoodOnly, setFreeFoodOnly] = useState(false);
  const trimmedQuery = query.trim();
  const hasActiveFilters =
    category !== "all" || trimmedQuery.length > 0 || freeFoodOnly;

  const filtered = useMemo(() => {
    return events.filter((ev) => {
      if (category !== "all" && ev.category !== category) return false;
      if (
        freeFoodOnly &&
        !ev.tags.includes("free food") &&
        ev.category !== "free_food"
      ) {
        return false;
      }
      if (trimmedQuery) {
        const q = trimmedQuery.toLowerCase();
        const hay = [
          ev.title,
          ev.description,
          ev.host,
          ev.location,
          ...ev.tags,
        ]
          .join(" ")
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [events, category, trimmedQuery, freeFoodOnly]);

  const grouped = useMemo(() => groupByDay(filtered), [filtered]);
  const dayKeys = Array.from(grouped.keys());
  const resultsLabel = hasActiveFilters
    ? `${filtered.length} matching ${filtered.length === 1 ? "event" : "events"}`
    : `${filtered.length} ${filtered.length === 1 ? "event" : "events"} indexed`;

  const clearFilters = () => {
    setCategory("all");
    setQuery("");
    setFreeFoodOnly(false);
  };

  return (
    <section id="events" className="mx-auto max-w-7xl px-4 pb-20 sm:px-6">
      {/* Filter bar */}
      <div className="sticky top-14 z-20 -mx-4 mb-10 border-b border-ink/10 bg-canvas/95 px-4 backdrop-blur sm:-mx-6 sm:px-6">
        {/* Row 1: view tabs */}
        <div className="flex items-end justify-end gap-4 pt-4">
          <div
            role="tablist"
            aria-label="Choose view"
            className="flex items-end gap-5"
          >
            <button
              type="button"
              role="tab"
              aria-selected={view === "list"}
              onClick={() => setView("list")}
              className="interactive-focus tab"
            >
              List
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === "calendar"}
              onClick={() => setView("calendar")}
              className="interactive-focus tab"
            >
              Calendar
            </button>
          </div>
        </div>

        {/* Row 2: category chips */}
        <div
          className="flex flex-wrap items-center gap-2 py-4"
          aria-label="Filter events by category"
        >
          {CATEGORIES.map((c) => {
            const active = category === c.value;
            return (
              <button
                type="button"
                key={c.value}
                onClick={() => setCategory(c.value)}
                aria-pressed={active}
                className={`interactive-focus inline-flex min-h-9 items-center border px-3 py-1.5 text-sm transition-colors ${
                  active
                    ? "border-ink bg-ink text-white"
                    : "border-ink/15 bg-canvas text-ink hover:border-ink"
                }`}
              >
                {c.label}
              </button>
            );
          })}
        </div>

        {/* Row 3: search + toggles */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-ink/10 py-4">
          <div className="relative flex-1 min-w-[220px]">
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
              placeholder="Search events, hosts, tags"
              aria-describedby="event-filter-summary"
              className="interactive-focus w-full border-b border-ink/15 bg-transparent py-2 pl-7 text-sm placeholder:text-muted focus:border-ink"
            />
          </div>
          <label className="interactive-focus inline-flex cursor-pointer select-none items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={freeFoodOnly}
              onChange={(e) => setFreeFoodOnly(e.target.checked)}
              className="h-4 w-4 accent-ink"
            />
            Free food only
          </label>
          <button
            type="button"
            onClick={clearFilters}
            disabled={!hasActiveFilters}
            className="interactive-focus text-sm font-medium text-ink underline-offset-4 hover:underline disabled:cursor-not-allowed disabled:text-muted disabled:no-underline"
          >
            Clear filters
          </button>
        </div>
      </div>

      {/* Results count */}
      <div
        id="event-filter-summary"
        className="mb-8 text-sm text-muted"
        aria-live="polite"
        aria-atomic="true"
      >
        {resultsLabel}
      </div>

      {view === "calendar" ? (
        <CalendarView events={filtered} />
      ) : (
        <>
          {dayKeys.length === 0 && (
            <div className="border border-dashed border-ink/15 px-6 py-20 text-center">
              <p className="font-display text-xl text-ink mb-1">No matches.</p>
              <p className="text-sm text-muted">
                Try a broader filter or clear your search.
              </p>
              <button
                type="button"
                onClick={clearFilters}
                className="interactive-focus mt-5 inline-flex min-h-11 items-center bg-ink px-5 py-2 text-sm font-medium text-white transition-opacity hover:opacity-85"
              >
                Clear filters
              </button>
            </div>
          )}

          {dayKeys.map((day) => {
            const dayEvents = grouped.get(day)!;
            return (
              <div key={day} className="mb-14">
                <div className="mb-5 flex items-baseline justify-between gap-4 border-b border-ink/10 pb-3">
                  <h3 className="font-display text-2xl font-semibold tracking-[-0.02em] text-ink">
                    {formatDay(day + "T12:00:00")}
                  </h3>
                  <span className="text-sm text-muted">
                    {dayEvents.length}{" "}
                    {dayEvents.length === 1 ? "event" : "events"}
                  </span>
                </div>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {dayEvents.map((ev) => (
                    <EventCard key={ev.id} event={ev} />
                  ))}
                </div>
              </div>
            );
          })}
        </>
      )}
    </section>
  );
}
