"use client";

import { useMemo, useState } from "react";
import type { CampusEvent } from "@/types/event";
import { CATEGORY_STYLES } from "../ui/CategoryBadge";
import { EventCard } from "./EventCard";
import {
  addPacificDays,
  addPacificMonths,
  formatPacificDayKey,
  formatPacificMonth,
  pacificDayKey,
  pacificDayOfMonth,
  pacificTodayKey,
  pacificWeekdayIndex,
  startOfPacificMonthKey,
} from "@/lib/dates";

const DAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const DOT_COLORS: Record<string, string> = {
  club: "bg-highlander",
  academic: "bg-leaf",
  social: "bg-coral",
  career: "bg-ink",
  sports: "bg-sky",
  arts: "bg-coral",
  community: "bg-leaf",
  free_food: "bg-gold",
};

export function CalendarView({ events }: { events: CampusEvent[] }) {
  const todayKey = useMemo(() => pacificTodayKey(), []);
  const [cursorKey, setCursorKey] = useState<string>(() =>
    startOfPacificMonthKey(todayKey)
  );
  const [selectedKey, setSelectedKey] = useState<string>(todayKey);

  const byDay = useMemo(() => {
    const map = new Map<string, CampusEvent[]>();
    for (const ev of events) {
      const key = pacificDayKey(ev.startsAt);
      const bucket = map.get(key);
      if (bucket) bucket.push(ev);
      else map.set(key, [ev]);
    }
    return map;
  }, [events]);

  const cells = useMemo(() => {
    const gridStart = addPacificDays(
      cursorKey,
      -pacificWeekdayIndex(cursorKey)
    );
    return Array.from({ length: 42 }, (_, i) => {
      return addPacificDays(gridStart, i);
    });
  }, [cursorKey]);

  const monthLabel = formatPacificMonth(cursorKey).toLowerCase();

  const selectedEvents = byDay.get(selectedKey) ?? [];
  const mobileAgendaDays = useMemo(
    () =>
      cells.filter((key) => {
        return (
          key.slice(0, 7) === cursorKey.slice(0, 7) &&
          (byDay.get(key)?.length ?? 0) > 0
        );
      }),
    [byDay, cells, cursorKey]
  );

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
      {/* Calendar */}
      <div className="overflow-hidden rounded-xl border border-ink/15 bg-canvas">
        <div className="flex items-baseline justify-between gap-3 border-b border-ink/10 px-5 py-4">
          <h3 className="font-display text-xl font-semibold tracking-[-0.02em] text-ink">
            {monthLabel}
          </h3>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => {
                setCursorKey(startOfPacificMonthKey(todayKey));
                setSelectedKey(todayKey);
              }}
              className="interactive-focus rounded-md border border-ink/15 px-3 py-1 text-sm transition-colors hover:border-ink"
            >
              Today
            </button>
            <button
              type="button"
              onClick={() => setCursorKey(addPacificMonths(cursorKey, -1))}
              aria-label="Previous month"
              className="interactive-focus inline-flex h-8 w-8 items-center justify-center rounded-md border border-ink/15 transition-colors hover:border-ink"
            >
              ‹
            </button>
            <button
              type="button"
              onClick={() => setCursorKey(addPacificMonths(cursorKey, 1))}
              aria-label="Next month"
              className="interactive-focus inline-flex h-8 w-8 items-center justify-center rounded-md border border-ink/15 transition-colors hover:border-ink"
            >
              ›
            </button>
          </div>
        </div>

        <div className="sm:hidden">
          {mobileAgendaDays.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <p className="text-sm text-muted">Nothing scheduled this month.</p>
            </div>
          ) : (
            <div className="divide-y divide-ink/10">
              {mobileAgendaDays.map((key) => {
                const dayEvents = byDay.get(key) ?? [];
                const categories = Array.from(
                  new Set(dayEvents.map((e) => e.category))
                ).slice(0, 4);
                const isSelected = key === selectedKey;

                return (
                  <section key={key} className="px-4 py-4">
                    <button
                      type="button"
                      onClick={() => setSelectedKey(key)}
                      aria-label={`Show events for ${formatPacificDayKey(key)}`}
                      className={[
                        "interactive-focus flex min-h-12 w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left transition-colors",
                        isSelected ? "bg-ink text-white" : "hover:bg-ink/[0.03]",
                      ].join(" ")}
                    >
                      <span>
                        <span
                          className={[
                            "block font-display text-lg font-semibold leading-tight",
                            isSelected ? "text-white" : "text-ink",
                          ].join(" ")}
                        >
                          {formatPacificDayKey(key)}
                        </span>
                        <span
                          className={[
                            "mt-1 block text-sm",
                            isSelected ? "text-white/70" : "text-muted",
                          ].join(" ")}
                        >
                          {dayEvents.length} {dayEvents.length === 1 ? "event" : "events"}
                        </span>
                      </span>
                      <span className="flex shrink-0 items-center gap-1">
                        {categories.map((c) => (
                          <span
                            key={c}
                            className={`h-2 w-2 ${
                              isSelected ? "bg-white/80" : DOT_COLORS[c] ?? "bg-ink"
                            }`}
                          />
                        ))}
                        {dayEvents.length > categories.length && (
                          <span
                            className={`font-mono text-[10px] ${
                              isSelected ? "text-white/70" : "text-muted"
                            }`}
                          >
                            +{dayEvents.length - categories.length}
                          </span>
                        )}
                      </span>
                    </button>
                    <div className="mt-3 grid gap-3">
                      {dayEvents.map((ev) => (
                        <EventCard key={ev.id} event={ev} compact />
                      ))}
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </div>

        <div className="hidden sm:block">
          <div className="grid grid-cols-7 border-b border-ink/10 bg-canvas">
            {DAY_LABELS.map((d) => (
              <div
                key={d}
                className="px-2 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-muted"
              >
                {d}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7">
            {cells.map((key, idx) => {
              const inMonth = key.slice(0, 7) === cursorKey.slice(0, 7);
              const isToday = key === todayKey;
              const isSelected = key === selectedKey;
              const dayEvents = byDay.get(key) ?? [];
              const categories = Array.from(
                new Set(dayEvents.map((e) => e.category))
              ).slice(0, 4);

              const lastCol = (idx + 1) % 7 === 0;
              const lastRow = idx >= 35;

              return (
                <button
                  type="button"
                  key={key}
                  onClick={() => setSelectedKey(key)}
                  className={[
                    "interactive-focus relative flex min-h-[88px] flex-col items-start gap-2 p-2 text-left transition-colors",
                    !lastCol ? "border-r" : "",
                    !lastRow ? "border-b" : "",
                    "border-ink/10",
                    isSelected ? "bg-ink text-white" : "hover:bg-ink/[0.03]",
                    !inMonth ? "opacity-40" : "",
                  ].join(" ")}
                >
                  <span
                    className={[
                      "font-mono text-xs leading-none",
                      isSelected ? "text-white/70" : "text-muted",
                    ].join(" ")}
                  >
                    {String(pacificDayOfMonth(key)).padStart(2, "0")}
                  </span>
                  <span
                    className={[
                      "font-display text-xl font-semibold tracking-[-0.02em] leading-none",
                      isSelected
                        ? "text-white"
                        : isToday
                          ? "text-ink underline underline-offset-4 decoration-2"
                          : "text-ink",
                    ].join(" ")}
                    aria-hidden
                  >
                    {pacificDayOfMonth(key)}
                  </span>

                  {dayEvents.length > 0 && (
                    <div className="mt-auto flex items-center gap-1">
                      {categories.map((c) => (
                        <span
                          key={c}
                          className={`h-1.5 w-1.5 ${
                            isSelected ? "bg-white/80" : DOT_COLORS[c] ?? "bg-ink"
                          }`}
                        />
                      ))}
                      {dayEvents.length > categories.length && (
                        <span
                          className={`font-mono text-[10px] ${
                            isSelected ? "text-white/70" : "text-muted"
                          }`}
                        >
                          +{dayEvents.length - categories.length}
                        </span>
                      )}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Legend */}
        <div className="hidden flex-wrap items-center gap-x-4 gap-y-2 border-t border-ink/10 px-5 py-3 font-mono text-[10px] uppercase tracking-[0.14em] text-muted sm:flex">
          {Object.entries(CATEGORY_STYLES).map(([key, s]) => (
            <span key={key} className="inline-flex items-center gap-1.5">
              <span className={`h-1.5 w-1.5 ${DOT_COLORS[key] ?? "bg-ink"}`} />
              {s.label}
            </span>
          ))}
        </div>
      </div>

      {/* Day detail */}
      <aside className="hidden space-y-4 sm:block">
        <div className="flex items-baseline justify-between gap-3 border-b border-ink/10 pb-3">
          <h3 className="font-display text-xl font-semibold tracking-[-0.02em] text-ink">
            {formatPacificDayKey(selectedKey)}
          </h3>
          <span className="text-sm text-muted">
            {selectedEvents.length}{" "}
            {selectedEvents.length === 1 ? "event" : "events"}
          </span>
        </div>
        {selectedEvents.length === 0 ? (
          <div className="rounded-xl border border-dashed border-ink/15 py-12 text-center">
            <p className="text-sm text-muted">Nothing scheduled.</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {selectedEvents.map((ev) => (
              <EventCard key={ev.id} event={ev} compact />
            ))}
          </div>
        )}
      </aside>
    </div>
  );
}
