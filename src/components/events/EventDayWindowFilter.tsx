"use client";

import { DAY_WINDOWS, type DayWindow } from "./events-filters";

type EventDayWindowFilterProps = {
  layout: "rail" | "sheet";
  dayWindow: DayWindow;
  onDayWindowChange: (next: DayWindow) => void;
};

const BUTTON_SIZE_CLASS = {
  rail: "min-h-8 px-3",
  sheet: "min-h-9 px-3.5",
} as const;

export function EventDayWindowFilter({
  layout,
  dayWindow,
  onDayWindowChange,
}: EventDayWindowFilterProps) {
  return (
    <div
      className="flex flex-wrap gap-1.5"
      role="group"
      aria-label="Filter events by time window"
    >
      {DAY_WINDOWS.map((w) => {
        const active = dayWindow === w.value;
        return (
          <button
            type="button"
            key={w.value}
            onClick={() => onDayWindowChange(w.value)}
            aria-pressed={active}
            className={[
              "interactive-focus inline-flex items-center rounded-full border py-1 text-[13px] transition-colors",
              BUTTON_SIZE_CLASS[layout],
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
  );
}
