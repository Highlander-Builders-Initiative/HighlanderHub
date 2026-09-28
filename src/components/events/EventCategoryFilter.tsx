"use client";

import { CATEGORY_PILL } from "@/lib/category-colors";
import type { EventCategory } from "@/types/event";
import { CATEGORIES, type CategoryValue } from "./events-filters";
import {
  EventFilterRow,
  FILTER_GROUP_CLASS,
  type FilterLayout,
} from "./EventFilterRow";

/** The selected row's label keeps its category's ink; "All" has none. */
function activeText(value: CategoryValue) {
  return value === "all" ? "text-ink" : CATEGORY_PILL[value as EventCategory].text;
}

/**
 * The selected row's background: a
 * category's own wash (the same one its tag pill wears on a card), or the
 * neutral fill for "All", which has no hue.
 */
function highlightClass(value: CategoryValue) {
  return value === "all"
    ? "bg-ink/[0.06]"
    : CATEGORY_PILL[value as EventCategory].highlight;
}

type EventCategoryFilterProps = {
  layout: FilterLayout;
  category: CategoryValue;
  onCategoryChange: (cat: CategoryValue) => void;
  counts: Map<CategoryValue, number>;
  /** Counts are still loading: show a placeholder instead of a misleading 0. */
  countsPending?: boolean;
};

export function EventCategoryFilter({
  layout,
  category,
  onCategoryChange,
  counts,
  countsPending = false,
}: EventCategoryFilterProps) {
  return (
    <div
      className={FILTER_GROUP_CLASS[layout]}
      role="group"
      aria-label="Filter events by category"
    >
      {CATEGORIES.map((c) => (
        <EventFilterRow
          key={c.value}
          id={c.value}
          layout={layout}
          pressed={category === c.value}
          selectedClass={`${highlightClass(c.value)} ${activeText(c.value)}`}
          onClick={() => onCategoryChange(c.value)}
          count={counts.get(c.value) ?? 0}
          countsPending={countsPending}
        >
          {c.label}
        </EventFilterRow>
      ))}
    </div>
  );
}
