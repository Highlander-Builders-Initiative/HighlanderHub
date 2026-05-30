"use client";

import { DAY_WINDOWS, type DayWindow } from "./events-filters";

type EventDayWindowFilterProps = {
  layout: "rail" | "sheet";
  dayWindow: DayWindow;
  onDayWindowChange: (next: DayWindow) => void;
};

// Four windows in one pill (All / Today / Week / Weekend). Short labels fit the
// narrow rail; the sheet uses the same track at a slightly larger text size.
const SEGMENT_TEXT_CLASS = {
  rail: "text-[12px]",
  sheet: "text-[13px]",
} as const;

/**
 * Segmented control: a single rounded track with one elevated thumb that
 * slides to the active window. The buttons sit transparently on top; only the
 * thumb moves, so switching reads as one continuous control rather than four
 * separate toggles.
 */
export function EventDayWindowFilter({
  layout,
  dayWindow,
  onDayWindowChange,
}: EventDayWindowFilterProps) {
  const activeIndex = Math.max(
    0,
    DAY_WINDOWS.findIndex((w) => w.value === dayWindow)
  );

  return (
    <div
      className="relative flex w-full rounded-full bg-ink/[0.05] p-1"
      role="group"
      aria-label="Filter events by time window"
    >
      {/* Sliding thumb: one segment wide, translated by whole segments. */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-y-1 left-1 rounded-full bg-canvas shadow-card transition-transform duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] motion-reduce:transition-none"
        style={{
          width: `calc((100% - 0.5rem) / ${DAY_WINDOWS.length})`,
          transform: `translateX(${activeIndex * 100}%)`,
        }}
      />

      {DAY_WINDOWS.map((w) => {
        const active = dayWindow === w.value;
        return (
          <button
            type="button"
            key={w.value}
            onClick={() => onDayWindowChange(w.value)}
            aria-pressed={active}
            className={[
              "interactive-focus relative z-10 min-w-0 flex-1 truncate rounded-full px-1.5 py-1.5 text-center font-medium transition-colors duration-200",
              SEGMENT_TEXT_CLASS[layout],
              active ? "text-ink" : "text-muted hover:text-ink",
            ].join(" ")}
          >
            {w.label}
          </button>
        );
      })}
    </div>
  );
}
