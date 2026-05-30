"use client";

import { EventCategoryFilter } from "./EventCategoryFilter";
import { GLASS_PANEL_CLASS } from "./glass-panel";
import type { CategoryValue } from "./events-filters";

type Props = {
  category: CategoryValue;
  onCategoryChange: (cat: CategoryValue) => void;
  counts: Map<CategoryValue, number>;
};

export function EventsLeftRail({ category, onCategoryChange, counts }: Props) {
  return (
    <div className={GLASS_PANEL_CLASS}>
      <p className="px-3 pb-2 text-[12px] font-medium text-muted">Browse</p>

      <EventCategoryFilter
        layout="rail"
        category={category}
        onCategoryChange={onCategoryChange}
        counts={counts}
      />
    </div>
  );
}
