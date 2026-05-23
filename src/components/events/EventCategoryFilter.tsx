"use client";

import { CATEGORY_RAIL } from "@/lib/category-colors";
import { CATEGORIES, type CategoryValue } from "./events-filters";

type EventCategoryFilterProps = {
  layout: "rail" | "grid";
  category: CategoryValue;
  onCategoryChange: (cat: CategoryValue) => void;
  counts: Map<CategoryValue, number>;
};

const GROUP_CLASS = {
  rail: "flex flex-col gap-0.5",
  grid: "grid grid-cols-2 gap-1.5",
} as const;

const BUTTON_BASE_CLASS = {
  rail: "interactive-focus flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-[14px] transition-colors",
  grid: "interactive-focus flex items-center gap-2 rounded-md border px-3 py-2 text-left text-[14px] transition-colors",
} as const;

const BUTTON_ACTIVE_CLASS = {
  rail: "bg-ink/[0.05] font-medium text-ink",
  grid: "border-ink bg-ink/[0.04] font-medium text-ink",
} as const;

const BUTTON_INACTIVE_CLASS = {
  rail: "text-ink/85 hover:bg-ink/[0.03] hover:text-ink",
  grid: "border-ink/15 text-ink/85 hover:border-ink",
} as const;

export function EventCategoryFilter({
  layout,
  category,
  onCategoryChange,
  counts,
}: EventCategoryFilterProps) {
  return (
    <div
      className={GROUP_CLASS[layout]}
      role="group"
      aria-label="Filter events by category"
    >
      {CATEGORIES.map((c) => {
        const active = category === c.value;
        const count = counts.get(c.value) ?? 0;
        const dotClass =
          c.value === "all" ? "bg-ink/30" : CATEGORY_RAIL[c.value];
        const countClass =
          layout === "rail"
            ? active
              ? "text-ink/70"
              : "text-muted/70"
            : "text-muted/80";

        return (
          <button
            type="button"
            key={c.value}
            onClick={() => onCategoryChange(c.value)}
            aria-pressed={active}
            className={[
              BUTTON_BASE_CLASS[layout],
              active
                ? BUTTON_ACTIVE_CLASS[layout]
                : BUTTON_INACTIVE_CLASS[layout],
            ].join(" ")}
          >
            <span
              aria-hidden
              className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotClass}`}
            />
            <span className="flex-1">{c.label}</span>
            <span
              className={`font-mono text-[11px] tabular-nums ${countClass}`}
            >
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
