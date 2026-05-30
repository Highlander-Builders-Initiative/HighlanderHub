"use client";

import { DAY_WINDOWS, type DayWindow } from "./events-filters";

type EventDayWindowFilterProps = {
  layout: "rail" | "sheet";
  dayWindow: DayWindow;
  onDayWindowChange: (next: DayWindow) => void;
};

// The narrow rail can't fit four labels in one row without truncating
// ("This week"), so it folds into a 2x2 grid; the wider sheet keeps the
// classic single-row segmented control.
const TRACK_CLASS = {
  rail: "grid grid-cols-2 gap-1 rounded-2xl bg-ink/[0.05] p-1",
  sheet: "flex rounded-full bg-ink/[0.05] p-1",
} as const;

const SEGMENT_CLASS = {
  rail: "rounded-xl py-1.5 px-2 text-[12px]",
  sheet: "flex-1 rounded-full py-1.5 px-2 text-[13px]",
} as const;

/**
 * Segmented control for the time window. A single rounded track with an
 * elevated canvas "thumb" under the active segment; the others stay quiet
 * until hovered.
 */
export function EventDayWindowFilter({
  layout,
  dayWindow,
  onDayWindowChange,
}: EventDayWindowFilterProps) {
  return (
    <div
      className={TRACK_CLASS[layout]}
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
              "interactive-focus min-w-0 truncate text-center font-medium transition-colors duration-200",
              SEGMENT_CLASS[layout],
              active
                ? "bg-canvas text-ink shadow-card"
                : "text-muted hover:text-ink",
            ].join(" ")}
          >
            {w.label}
          </button>
        );
      })}
    </div>
  );
}
