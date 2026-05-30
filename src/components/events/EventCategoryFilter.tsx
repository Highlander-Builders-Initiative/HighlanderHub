"use client";

import { ALL_PILL, CATEGORY_PILL } from "@/lib/category-colors";
import { CATEGORIES, type CategoryValue } from "./events-filters";

type EventCategoryFilterProps = {
  layout: "rail" | "grid";
  category: CategoryValue;
  onCategoryChange: (cat: CategoryValue) => void;
  counts: Map<CategoryValue, number>;
};

const GROUP_CLASS = {
  rail: "flex flex-col gap-1",
  grid: "grid grid-cols-2 gap-1.5",
} as const;

const BUTTON_BASE_CLASS = {
  rail: "interactive-focus flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-[14px] transition-colors",
  grid: "interactive-focus flex items-center gap-2 rounded-xl px-3 py-2.5 text-left text-[14px] transition-colors",
} as const;

function pillState(value: CategoryValue) {
  return value === "all" ? ALL_PILL : CATEGORY_PILL[value];
}

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
        const { hover, active: activeClass } = pillState(c.value);

        return (
          <button
            type="button"
            key={c.value}
            onClick={() => onCategoryChange(c.value)}
            aria-pressed={active}
            className={[
              BUTTON_BASE_CLASS[layout],
              active
                ? `${activeClass} font-medium`
                : `text-ink/80 ${hover}`,
            ].join(" ")}
          >
            <span className="min-w-0 flex-1 truncate">{c.label}</span>
            <span
              className={`font-mono text-[11px] tabular-nums ${
                active ? "opacity-60" : "text-muted/80"
              }`}
            >
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
