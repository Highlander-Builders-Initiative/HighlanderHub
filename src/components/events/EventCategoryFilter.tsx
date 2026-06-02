"use client";

import { AnimatedBackground } from "@/components/core/animated-background";
import { ALL_PILL, CATEGORY_PILL } from "@/lib/category-colors";
import type { EventCategory } from "@/types/event";
import { CATEGORIES, type CategoryValue } from "./events-filters";

function pillColors(value: CategoryValue) {
  return value === "all" ? ALL_PILL : CATEGORY_PILL[value as EventCategory];
}

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

const BUTTON_CLASS = {
  rail: "rounded-xl px-3 py-2 text-[14px]",
  grid: "rounded-xl px-3 py-2.5 text-[14px]",
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
      <AnimatedBackground
        defaultValue={category}
        enableHover
        className={(id) =>
          `rounded-xl ${pillColors((id ?? "all") as CategoryValue).highlight}`
        }
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
                  ? `${pillColors(c.value).text} font-medium`
                  : "text-ink/80 hover:text-ink"
              }`}
            >
              <span className="min-w-0 flex-1 truncate text-left">
                {c.label}
              </span>
              <span
                className={`pl-2 font-mono text-[11px] tabular-nums ${
                  active ? "text-muted" : "text-muted/80"
                }`}
              >
                {count}
              </span>
            </button>
          );
        })}
      </AnimatedBackground>
    </div>
  );
}
