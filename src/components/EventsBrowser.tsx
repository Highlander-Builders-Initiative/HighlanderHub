"use client";

import { useState, useMemo } from "react";
import type { CampusEvent, EventCategory } from "@/types/event";
import { EventCard } from "./EventCard";
import { formatDay } from "@/lib/dates";
import { groupByDay } from "@/lib/events";

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

  const filtered = useMemo(() => {
    return events.filter((ev) => {
      if (category !== "all" && ev.category !== category) return false;
      if (freeFoodOnly && !ev.tags.includes("free food") && ev.category !== "free_food") {
        return false;
      }
      if (query.trim()) {
        const q = query.toLowerCase();
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
  }, [events, category, query, freeFoodOnly]);

  const grouped = useMemo(() => groupByDay(filtered), [filtered]);
  const dayKeys = Array.from(grouped.keys());

  return (
    <section id="events" className="mx-auto max-w-7xl px-6 pb-16">
      {/* Filter bar */}
      <div className="sticky top-16 z-20 -mx-6 px-6 py-4 bg-canvas/85 backdrop-blur border-b border-line mb-8">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            {CATEGORIES.map((c) => (
              <button
                key={c.value}
                onClick={() => setCategory(c.value)}
                className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${
                  category === c.value
                    ? "bg-ink text-white border-ink"
                    : "bg-canvas text-ink border-line hover:border-ink/30"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <div className="relative flex-1 min-w-[220px]">
              <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted text-sm">
                ⌕
              </span>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search events, hosts, tags…"
                className="w-full rounded-full border border-line bg-canvas pl-9 pr-4 py-2.5 text-sm placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-highlander/30 focus:border-highlander"
              />
            </div>
            <label className="inline-flex items-center gap-2 text-sm text-ink cursor-pointer select-none">
              <input
                type="checkbox"
                checked={freeFoodOnly}
                onChange={(e) => setFreeFoodOnly(e.target.checked)}
                className="accent-highlander h-4 w-4"
              />
              Free food only
            </label>
          </div>
        </div>
      </div>

      {/* Results count */}
      <div className="mb-6 text-sm text-muted">
        {filtered.length} event{filtered.length === 1 ? "" : "s"}
      </div>

      {dayKeys.length === 0 && (
        <div className="rounded-2xl border border-dashed border-line py-20 text-center">
          <p className="font-display text-xl text-ink mb-1">No matches</p>
          <p className="text-sm text-muted">Try a broader filter or clear your search.</p>
        </div>
      )}

      {dayKeys.map((day) => {
        const dayEvents = grouped.get(day)!;
        return (
          <div key={day} className="mb-12">
            <div className="flex items-baseline gap-3 mb-5">
              <h2 className="font-display text-2xl font-semibold tracking-tight text-ink">
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
