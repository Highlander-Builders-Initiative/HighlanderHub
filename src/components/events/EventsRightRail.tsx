"use client";

import type { EventCategory } from "@/types/event";
import { EventsMiniCalendar } from "./EventsMiniCalendar";
import { DAY_WINDOWS, type DayWindow } from "./events-filters";

type Props = {
  cursor: string;
  onCursorChange: (next: string) => void;
  todayKey: string;
  selectedKey: string;
  onSelect: (dayKey: string) => void;
  categoriesByDay: Map<string, EventCategory[]>;
  dayWindow: DayWindow;
  onDayWindowChange: (next: DayWindow) => void;
};

export function EventsRightRail({
  cursor,
  onCursorChange,
  todayKey,
  selectedKey,
  onSelect,
  categoriesByDay,
  dayWindow,
  onDayWindowChange,
}: Props) {
  return (
    <div>
      <EventsMiniCalendar
        cursor={cursor}
        onCursorChange={onCursorChange}
        todayKey={todayKey}
        selectedKey={selectedKey}
        onSelect={onSelect}
        categoriesByDay={categoriesByDay}
      />

      <div className="my-5 h-px bg-ink/10" />

      <p className="px-1 pb-2 text-[12px] font-medium text-muted">When</p>

      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter events by time window">
        {DAY_WINDOWS.map((w) => {
          const active = dayWindow === w.value;
          return (
            <button
              type="button"
              key={w.value}
              onClick={() => onDayWindowChange(w.value)}
              aria-pressed={active}
              className={[
                "interactive-focus inline-flex min-h-8 items-center rounded-full border px-3 py-1 text-[13px] transition-colors",
                active
                  ? "border-ink bg-ink text-canvas"
                  : "border-ink/15 bg-canvas text-ink hover:border-ink",
              ].join(" ")}
            >
              {w.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
