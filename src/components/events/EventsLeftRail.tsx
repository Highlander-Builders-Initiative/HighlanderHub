"use client";

import { EventCategoryFilter } from "./EventCategoryFilter";
import type { CategoryValue } from "./events-filters";

type Props = {
  category: CategoryValue;
  onCategoryChange: (cat: CategoryValue) => void;
  counts: Map<CategoryValue, number>;
};

export function EventsLeftRail({
  category,
  onCategoryChange,
  counts,
}: Props) {
  return (
    // No panel: the rails sit on the page, so the event cards are the only
    // boxes on it (DESIGN.md, The One-Surface Rule).
    <div>
      <p className="px-3 pb-2 text-[12px] font-medium text-muted">Topics</p>

      <EventCategoryFilter
        layout="rail"
        category={category}
        onCategoryChange={onCategoryChange}
        counts={counts}
      />
    </div>
  );
}
