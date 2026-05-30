"use client";

import { EventDayWindowFilter } from "./EventDayWindowFilter";
import { EventsMiniCalendar } from "./EventsMiniCalendar";
import { GLASS_PANEL_CLASS } from "./glass-panel";
import type { DayWindow } from "./events-filters";

type Props = {
  cursor: string;
  onCursorChange: (next: string) => void;
  todayKey: string;
  selectedKey: string;
  onSelect: (dayKey: string) => void;
  countsByDay: Map<string, number>;
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
  countsByDay,
  isLoading,
  dayWindow,
  onDayWindowChange,
}: Props) {
  return (
    <div className={GLASS_PANEL_CLASS}>
      <EventsMiniCalendar
        cursor={cursor}
        onCursorChange={onCursorChange}
        todayKey={todayKey}
        selectedKey={selectedKey}
        onSelect={onSelect}
        countsByDay={countsByDay}
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
