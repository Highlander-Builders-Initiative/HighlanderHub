"use client";

import { useState, useMemo } from "react";
import type { CampusEvent, EventCategory } from "@/types/event";
import { EventCard } from "./EventCard";
import { formatDay } from "@/lib/dates";
import { groupByDay } from "@/lib/event-grouping";

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
  const [category, setCategory] = useState<EventCategory | "all">("all");
  const [query, setQuery] = useState("");
  const [freeFoodOnly, setFreeFoodOnly] = useState(false);
  const trimmedQuery = query.trim();
  const hasActiveFilters = category !== "all" || trimmedQuery.length > 0 || freeFoodOnly;

  const filtered = useMemo(() => {
    return events.filter((ev) => {
      if (category !== "all" && ev.category !== category) return false;
      if (freeFoodOnly && !ev.tags.includes("free food") && ev.category !== "free_food") {
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
  const resultsLabel = `Showing ${filtered.length} event${
    filtered.length === 1 ? "" : "s"
  }${hasActiveFilters ? " matching your filters" : ""}`;

  const clearFilters = () => {
    setCategory("all");
    setQuery("");
    setFreeFoodOnly(false);
  };

  return (
    <section id="events" className="mx-auto max-w-7xl px-4 pb-16 sm:px-6">
      {/* Filter bar */}
      <div className="sticky top-[7.75rem] z-20 -mx-4 mb-8 border-b border-line bg-canvas/90 px-4 py-4 backdrop-blur sm:-mx-6 sm:px-6 md:top-16">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2" aria-label="Filter events by category">
            {CATEGORIES.map((c) => (
              <button
                type="button"
                key={c.value}
                onClick={() => setCategory(c.value)}
                aria-pressed={category === c.value}
                className={`interactive-focus min-h-11 rounded-full border px-4 py-2 text-sm transition-colors ${
                  category === c.value
                    ? "bg-ink text-white border-ink"
                    : "bg-canvas text-ink border-line hover:border-ink/30"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-3">
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
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
              >
                <circle cx="11" cy="11" r="7" />
                <path d="m20 20-3.5-3.5" />
              </svg>
              <input
                id="event-search"
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search events, hosts, tags…"
                aria-describedby="event-filter-summary"
                className="interactive-focus min-h-11 w-full rounded-full border border-line bg-canvas py-2.5 pl-10 pr-4 text-sm placeholder:text-muted focus:border-highlander"
              />
            </div>
            <label className="interactive-focus inline-flex min-h-11 cursor-pointer select-none items-center gap-2 rounded-full border border-line bg-canvas px-3 text-sm text-ink hover:border-ink/30">
              <input
                type="checkbox"
                checked={freeFoodOnly}
                onChange={(e) => setFreeFoodOnly(e.target.checked)}
                className="h-5 w-5 accent-highlander"
              />
              Free food only
            </label>
            <button
              type="button"
              onClick={clearFilters}
              disabled={!hasActiveFilters}
              className="interactive-focus min-h-11 rounded-full border border-line px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-ink/30 disabled:cursor-not-allowed disabled:opacity-45"
            >
              Clear filters
            </button>
          </div>
        </div>
      </div>

      {/* Results count */}
      <div
        id="event-filter-summary"
        className="mb-6 text-sm text-muted"
        aria-live="polite"
        aria-atomic="true"
      >
        {resultsLabel}
      </div>

      {dayKeys.length === 0 && (
        <div className="rounded-xl border border-dashed border-line px-6 py-20 text-center">
          <p className="font-display text-xl text-ink mb-1">No matches</p>
          <p className="text-sm text-muted">Try a broader filter or clear your search.</p>
          <button
            type="button"
            onClick={clearFilters}
            className="interactive-focus mt-5 min-h-11 rounded-full bg-ink px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-highlander"
          >
            Clear filters
          </button>
        </div>
      )}

      {dayKeys.map((day) => {
        const dayEvents = grouped.get(day)!;
        return (
          <div key={day} className="mb-12">
            <div className="flex items-baseline gap-3 mb-5">
              <h2 className="font-display text-2xl font-semibold text-ink">
                {formatDay(day + "T12:00:00")}
              </h2>
              <span className="text-xs text-muted">
                {dayEvents.length} event{dayEvents.length === 1 ? "" : "s"}
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
    </section>
  );
}
