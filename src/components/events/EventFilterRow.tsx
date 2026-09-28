"use client";

import type { ReactNode } from "react";

export type FilterLayout = "rail" | "grid";

export const FILTER_GROUP_CLASS = {
  rail: "flex flex-col gap-1",
  grid: "grid grid-cols-2 gap-1.5",
} as const;

const ROW_CLASS = {
  rail: "rounded-xl px-3 py-2 text-[14px]",
  grid: "rounded-xl px-3 py-2.5 text-[14px]",
} as const;

type EventFilterRowProps = {
  layout: FilterLayout;
  id: string;
  pressed: boolean;
  /** The pressed row's background and label color. */
  selectedClass: string;
  onClick: () => void;
  count: number;
  /** Counts are still loading: show a placeholder instead of a misleading 0. */
  countsPending?: boolean;
  /** A mark before the label, such as a switch's check box. */
  leading?: ReactNode;
  children: ReactNode;
};

/**
 * One row of a rail filter (Topics, Only show, Hosted by): its label, then
 * how many events choosing it would show. Hover is an instant neutral wash.
 */
export function EventFilterRow({
  layout,
  id,
  pressed,
  selectedClass,
  onClick,
  count,
  countsPending = false,
  leading,
  children,
}: EventFilterRowProps) {
  return (
    <button
      data-id={id}
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={`interactive-focus flex w-full items-center ${ROW_CLASS[layout]} ${
        pressed
          ? `${selectedClass} font-medium`
          : "text-ink/80 hover:bg-ink/[0.04] hover:text-ink"
      }`}
    >
      {leading}
      <span className="min-w-0 flex-1 truncate text-left">{children}</span>
      <span
        className={`pl-2 text-[11px] tabular-nums ${
          pressed ? "text-muted" : "text-muted/80"
        }`}
      >
        {countsPending ? (
          <span
            aria-hidden
            className="skeleton inline-block h-2 w-3.5 rounded-full bg-ink/10 align-middle"
          />
        ) : (
          count
        )}
      </span>
    </button>
  );
}
