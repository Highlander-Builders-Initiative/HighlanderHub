"use client";

import { useMemo } from "react";
import {
  addPacificDays,
  addPacificMonths,
  formatPacificMonth,
  pacificCalendarGridRange,
  pacificDayOfMonth,
  startOfPacificMonthKey,
} from "@/lib/dates";

const DAY_INITIALS = ["s", "m", "t", "w", "t", "f", "s"];

// Heat map: event count buckets to a single iris wash that deepens with the
// day's load. No category hue here, so a busy day reads as one calm signal
// instead of a row of competing dots.
function heatClass(count: number): string {
  if (count >= 6) return "bg-highlander/[0.24]";
  if (count >= 3) return "bg-highlander/[0.15]";
  if (count >= 1) return "bg-highlander/[0.07]";
  return "";
}

type Props = {
  cursor: string;
  onCursorChange: (next: string) => void;
  todayKey: string;
  selectedKey: string;
  onSelect: (dayKey: string) => void;
  countsByDay: Map<string, number>;
  isLoading: boolean;
};

export function EventsMiniCalendar({
  cursor,
  onCursorChange,
  todayKey,
  selectedKey,
  onSelect,
  countsByDay,
  isLoading,
}: Props) {
  const monthKey = cursor.slice(0, 7);

  const cells = useMemo(() => {
    const { start } = pacificCalendarGridRange(cursor);
    const all = Array.from({ length: 42 }, (_, i) => addPacificDays(start, i));
    // Render only as many weeks as the month needs. A fixed 6-row grid leaves a
    // fat gap of next-month days for short months (e.g. Feb 2026 starts on a
    // Sunday and ends in 4 rows); trim any trailing week with no in-month day.
    let lastInMonth = 0;
    for (let i = 0; i < all.length; i++) {
      if (all[i].slice(0, 7) === monthKey) lastInMonth = i;
    }
    const weeks = Math.ceil((lastInMonth + 1) / 7);
    return all.slice(0, weeks * 7);
  }, [cursor, monthKey]);

  const monthLabel = formatPacificMonth(cursor).toLowerCase();

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="min-w-0 font-display text-base font-semibold tracking-[-0.015em] text-ink">
          {monthLabel}
        </h2>
        <div className="flex items-center gap-0.5">
          <button
            type="button"
            onClick={() => onCursorChange(startOfPacificMonthKey(todayKey))}
            className="interactive-focus inline-flex h-7 items-center rounded-md px-2.5 text-[12px] font-medium text-muted transition-colors hover:bg-ink/[0.04] hover:text-ink"
          >
            Today
          </button>
          <button
            type="button"
            onClick={() => onCursorChange(addPacificMonths(cursor, -1))}
            aria-label="Previous month"
            className="interactive-focus inline-flex h-7 w-7 items-center justify-center rounded-md text-muted transition-colors hover:bg-ink/[0.04] hover:text-ink"
          >
            ‹
          </button>
          <button
            type="button"
            onClick={() => onCursorChange(addPacificMonths(cursor, 1))}
            aria-label="Next month"
            className="interactive-focus inline-flex h-7 w-7 items-center justify-center rounded-md text-muted transition-colors hover:bg-ink/[0.04] hover:text-ink"
          >
            ›
          </button>
        </div>
      </div>

      <div
        aria-busy={isLoading}
        className={`transition-opacity duration-[250ms] ease-[cubic-bezier(0.16,1,0.3,1)] ${
          isLoading ? "opacity-60" : "opacity-100"
        }`}
      >
        <div className="grid grid-cols-7 text-center">
          {DAY_INITIALS.map((d, i) => (
            <span
              key={i}
              aria-hidden
              className="pb-1.5 text-[10px] font-medium text-muted/80"
            >
              {d}
            </span>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-y-1">
          {cells.map((key) => {
            const inMonth = key.slice(0, 7) === monthKey;
            const isToday = key === todayKey;
            const isSelected = key === selectedKey;
            const count = countsByDay.get(key) ?? 0;
            // Heat only paints the focused month; adjacent-month days stay
            // quiet so the eye holds on the current grid.
            const heat = !isLoading && inMonth ? heatClass(count) : "";

            return (
              <button
                type="button"
                key={key}
                onClick={() => onSelect(key)}
                aria-label={`Jump to ${key}, ${
                  count === 0 ? "no events" : `${count} ${count === 1 ? "event" : "events"}`
                }`}
                aria-pressed={isSelected}
                className={[
                  "interactive-focus relative mx-auto flex h-9 w-9 items-center justify-center rounded-md text-[13px] transition-colors",
                  isSelected
                    ? "bg-ink text-canvas"
                    : inMonth
                      ? `text-ink ${heat || "hover:bg-ink/[0.04]"} ${heat ? "hover:bg-highlander/[0.28]" : ""}`
                      : "text-muted/45 hover:bg-ink/[0.04]",
                ].join(" ")}
              >
                <span
                  className={[
                    "leading-none tabular-nums",
                    isToday && !isSelected ? "font-semibold underline underline-offset-[3px] decoration-1" : "",
                  ].join(" ")}
                >
                  {pacificDayOfMonth(key)}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
