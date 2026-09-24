"use client";

import { AnimatedBackground } from "@/components/core/animated-background";
import { CATEGORY_PILL } from "@/lib/category-colors";
import type { EventCategory } from "@/types/event";
import { CATEGORIES, type CategoryValue } from "./events-filters";

/** The selected row's label keeps its category's ink; "All" has none. */
function activeText(value: CategoryValue) {
  return value === "all" ? "text-ink" : CATEGORY_PILL[value as EventCategory].text;
}

/**
 * The sliding highlight under the hovered, then the selected, row: a
 * category's own wash (the same one its tag pill wears on a card), or the
 * neutral fill for "All", which has no hue.
 */
function highlightClass(value: CategoryValue) {
  return value === "all"
    ? "bg-ink/[0.06]"
    : CATEGORY_PILL[value as EventCategory].highlight;
}

type EventCategoryFilterProps = {
  layout: "rail" | "grid";
  category: CategoryValue;
  onCategoryChange: (cat: CategoryValue) => void;
  counts: Map<CategoryValue, number>;
  /** Counts are still loading: show a placeholder instead of a misleading 0. */
  countsPending?: boolean;
};

const GROUP_CLASS = {
  rail: "flex flex-col gap-1",
  grid: "grid grid-cols-2 gap-1.5",
} as const;

const BUTTON_CLASS = {
  rail: "rounded-xl px-3 py-2 text-[14px]",
  grid: "rounded-xl px-3 py-2.5 text-[14px]",
} as const;

export function EventCategoryFilter({
  layout,
  category,
  onCategoryChange,
  counts,
  countsPending = false,
}: EventCategoryFilterProps) {
  return (
    <div
      className={GROUP_CLASS[layout]}
      role="group"
      aria-label="Filter events by category"
    >
      <AnimatedBackground
        defaultValue={category}
        enableHover
        className={(id) => `rounded-xl ${highlightClass((id ?? "all") as CategoryValue)}`}
        transition={{ type: "spring", bounce: 0.2, duration: 0.3 }}
      >
        {CATEGORIES.map((c) => {
          const active = category === c.value;
          const count = counts.get(c.value) ?? 0;
          return (
            <button
              key={c.value}
              data-id={c.value}
              type="button"
              aria-pressed={active}
              onClick={() => onCategoryChange(c.value)}
              className={`interactive-focus w-full transition-colors ${BUTTON_CLASS[layout]} ${
                active
                  ? `${activeText(c.value)} font-medium`
                  : "text-ink/80 hover:text-ink"
              }`}
            >
              <span className="min-w-0 flex-1 truncate text-left">
                {c.label}
              </span>
              <span
                className={`pl-2 text-[11px] tabular-nums ${
                  active ? "text-muted" : "text-muted/80"
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
        })}
      </AnimatedBackground>
    </div>
  );
}
