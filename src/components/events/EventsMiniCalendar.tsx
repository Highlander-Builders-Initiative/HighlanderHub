"use client";

import { useMemo } from "react";
import type { EventCategory } from "@/types/event";
import { CATEGORY_RAIL } from "@/lib/category-colors";
import {
  addPacificDays,
  addPacificMonths,
  formatPacificMonth,
  pacificCalendarGridRange,
  pacificDayOfMonth,
  startOfPacificMonthKey,
} from "@/lib/dates";

const DAY_INITIALS = ["s", "m", "t", "w", "t", "f", "s"];

type Props = {
  cursor: string;
  onCursorChange: (next: string) => void;
  todayKey: string;
  selectedKey: string;
  onSelect: (dayKey: string) => void;
  categoriesByDay: Map<string, EventCategory[]>;
  isLoading: boolean;
};

export function EventsMiniCalendar({
  cursor,
  onCursorChange,
  todayKey,
  selectedKey,
  onSelect,
  categoriesByDay,
  isLoading,
}: Props) {
  const cells = useMemo(() => {
    const { start } = pacificCalendarGridRange(cursor);
    return Array.from({ length: 42 }, (_, i) => addPacificDays(start, i));
  }, [cursor]);

  const monthLabel = formatPacificMonth(cursor).toLowerCase();
  const monthKey = cursor.slice(0, 7);

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
            const dayEvents = categoriesByDay.get(key) ?? [];
            const dots = dayEvents.slice(0, 3);

            return (
              <button
                type="button"
                key={key}
                onClick={() => onSelect(key)}
                aria-label={`Jump to ${key}`}
                aria-pressed={isSelected}
                className={[
                  "interactive-focus relative mx-auto flex h-9 w-9 flex-col items-center justify-center rounded-md text-[13px] transition-colors",
                  isSelected
                    ? "bg-ink text-canvas"
                    : isToday
                      ? "text-ink"
                      : inMonth
                        ? "text-ink hover:bg-ink/[0.04]"
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
                {!isLoading && dots.length > 0 && (
                  <span
                    aria-hidden
                    className="absolute bottom-1 flex items-center gap-[2px]"
                  >
                    {dots.map((c, i) => (
                      <span
                        key={`${c}-${i}`}
                        className={`block h-1 w-1 rounded-full ${
                          isSelected ? "bg-canvas/80" : CATEGORY_RAIL[c]
                        }`}
                      />
                    ))}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
