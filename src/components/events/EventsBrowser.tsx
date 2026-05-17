"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import type { CampusEvent, EventCategory } from "@/types/event";
import { EventCard } from "./EventCard";
import { CalendarView } from "./CalendarView";
import { SubmitEventCta } from "./SubmitEventCta";
import { formatDay } from "@/lib/dates";
import { groupByDay } from "@/lib/event-grouping";
import { track } from "@/lib/analytics";

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
  const trimmedQuery = query.trim();
  const hasActiveFilters = category !== "all" || trimmedQuery.length > 0;

  const filtered = useMemo(() => {
    return events.filter((ev) => {
      if (category === "free_food") {
        if (ev.category !== "free_food" && !ev.tags.includes("free food")) {
          return false;
        }
      } else if (category !== "all" && ev.category !== category) {
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
  }, [events, category, trimmedQuery]);

  const grouped = useMemo(() => groupByDay(filtered), [filtered]);
  const dayKeys = Array.from(grouped.keys());
  const resultsLabel = hasActiveFilters
    ? `${filtered.length} matching ${filtered.length === 1 ? "event" : "events"}`
    : `${filtered.length} ${filtered.length === 1 ? "event" : "events"} indexed`;

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

  return (
    <section id="events" className="mx-auto max-w-7xl px-4 pb-20 sm:px-6">
      {/* Filter bar */}
      <div
        className="sticky z-20 -mx-4 mb-8 border-b border-ink/10 bg-canvas/95 px-4 backdrop-blur transition-[top] duration-200 ease-out sm:-mx-6 sm:px-6"
        style={{ top: "var(--masthead-h, 56px)" }}
      >
        {/* Row 1: view toggle + search */}
        <div className="flex items-center gap-3 pt-3 sm:pt-4">
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

        {/* Row 2: category chips */}
        <div
          className="flex flex-wrap items-center gap-1.5 py-3"
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
                    : "border-ink/15 bg-canvas text-ink hover:border-ink"
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
                <div className="grid items-start gap-3 md:grid-cols-2 md:gap-4 lg:grid-cols-3">
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
