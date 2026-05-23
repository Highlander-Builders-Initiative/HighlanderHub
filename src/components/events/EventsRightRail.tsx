"use client";

import type { EventCategory } from "@/types/event";
import { EventDayWindowFilter } from "./EventDayWindowFilter";
import { EventsMiniCalendar } from "./EventsMiniCalendar";
import type { DayWindow } from "./events-filters";

type Props = {
  cursor: string;
  onCursorChange: (next: string) => void;
  todayKey: string;
  selectedKey: string;
  onSelect: (dayKey: string) => void;
  categoriesByDay: Map<string, EventCategory[]>;
  isLoading: boolean;
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
  isLoading,
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
        isLoading={isLoading}
      />

      <div className="my-5 h-px bg-ink/10" />

      <p className="px-1 pb-2 text-[12px] font-medium text-muted">When</p>

      <EventDayWindowFilter
        layout="rail"
        dayWindow={dayWindow}
        onDayWindowChange={onDayWindowChange}
      />
    </div>
  );
}
