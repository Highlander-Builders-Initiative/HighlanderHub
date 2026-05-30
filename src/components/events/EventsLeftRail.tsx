"use client";

import { EventCategoryFilter } from "./EventCategoryFilter";
import type { CategoryValue } from "./events-filters";

type Props = {
  category: CategoryValue;
  onCategoryChange: (cat: CategoryValue) => void;
  counts: Map<CategoryValue, number>;
};

export function EventsLeftRail({ category, onCategoryChange, counts }: Props) {
  return (
    <div>
      <p className="px-2.5 pb-2 text-[12px] font-medium text-muted">Browse</p>

      <EventCategoryFilter
        layout="rail"
        category={category}
        onCategoryChange={onCategoryChange}
        counts={counts}
      />
    </div>
  );
}
