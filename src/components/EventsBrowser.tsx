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
    <section className="mx-auto max-w-7xl px-6 py-10">
      {/* Filter bar */}
      <div className="border-y-2 border-ink py-4 mb-10 flex flex-col gap-4">
        <div className="flex items-center gap-4 flex-wrap">
          <span className="font-mono text-[11px] uppercase tracking-widest text-ink/60">
            Filter:
          </span>
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((c) => (
              <button
                key={c.value}
                onClick={() => setCategory(c.value)}
                className={`font-mono text-[11px] uppercase tracking-widest px-3 py-1.5 border transition-colors ${
                  category === c.value
                    ? "bg-ink text-bone border-ink"
                    : "border-ink/30 hover:border-ink"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-4 flex-wrap">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search events, hosts, tags..."
            className="flex-1 min-w-[200px] bg-transparent border-b border-ink py-2 px-1 font-body text-lg placeholder:text-ink/40 focus:outline-none focus:border-clay"
          />
          <label className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest cursor-pointer">
            <input
              type="checkbox"
              checked={freeFoodOnly}
              onChange={(e) => setFreeFoodOnly(e.target.checked)}
              className="accent-clay"
            />
            Free food only
          </label>
        </div>
      </div>

      {/* Results count */}
      <div className="mb-6 font-mono text-xs uppercase tracking-widest text-ink/60">
        {filtered.length} event{filtered.length === 1 ? "" : "s"} found
      </div>

      {/* Grouped by day */}
      {dayKeys.length === 0 && (
        <div className="py-16 text-center">
          <p className="font-display italic text-3xl text-ink/40">
            Nothing matches that. Try a broader filter.
          </p>
        </div>
      )}

      {dayKeys.map((day) => {
        const dayEvents = grouped.get(day)!;
        return (
          <div key={day} className="mb-12">
            <div className="flex items-baseline gap-4 mb-5 pb-2 border-b border-ink">
              <h2 className="font-display text-3xl font-medium">
                {formatDay(day + "T12:00:00")}
              </h2>
              <span className="font-mono text-xs uppercase tracking-widest text-ink/60">
                {dayEvents.length} event{dayEvents.length === 1 ? "" : "s"}
              </span>
            </div>
            <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
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
