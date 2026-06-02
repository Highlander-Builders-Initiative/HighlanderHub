"use client";

import { AnimatedBackground } from "@/components/core/animated-background";
import { DAY_WINDOWS, type DayWindow } from "./events-filters";

type EventDayWindowFilterProps = {
  layout: "rail" | "sheet";
  dayWindow: DayWindow;
  onDayWindowChange: (next: DayWindow) => void;
};

const TEXT_SIZE_CLASS = {
  rail: "text-[12px]",
  sheet: "text-[13px]",
} as const;

/**
 * Segmented control for the time window. One rounded track with a canvas
 * "thumb" that springs to the selected window via the shared AnimatedBackground
 * (same motion system as the Topics list and the calendar nav).
 */
export function EventDayWindowFilter({
  layout,
  dayWindow,
  onDayWindowChange,
}: EventDayWindowFilterProps) {
  return (
    <div
      className="flex w-full rounded-full bg-ink/[0.05] p-1"
      role="group"
      aria-label="Filter events by time window"
    >
      <AnimatedBackground
        defaultValue={dayWindow}
        enableHover
        className="rounded-full bg-canvas shadow-card"
        transition={{ type: "spring", bounce: 0.2, duration: 0.3 }}
      >
        {DAY_WINDOWS.map((w) => {
          const active = dayWindow === w.value;
          return (
            <button
              key={w.value}
              data-id={w.value}
              type="button"
              aria-pressed={active}
              onClick={() => onDayWindowChange(w.value)}
              className={`interactive-focus flex-1 rounded-full py-1.5 font-medium transition-colors ${
                TEXT_SIZE_CLASS[layout]
              } ${active ? "text-ink" : "text-muted hover:text-ink"}`}
            >
              {w.label}
            </button>
          );
        })}
      </AnimatedBackground>
    </div>
  );
}
