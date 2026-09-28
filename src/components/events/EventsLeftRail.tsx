"use client";

import { EventCategoryFilter } from "./EventCategoryFilter";
import { EventFeedSwitches } from "./EventFeedSwitches";
import { EventHostGroupFilter } from "./EventHostGroupFilter";
import type {
  CategoryValue,
  EventFacetCounts,
  EventFeedFacets,
} from "./events-filters";

type Props = {
  category: CategoryValue;
  onCategoryChange: (cat: CategoryValue) => void;
  facets: EventFeedFacets;
  onFacetsChange: (next: Partial<EventFeedFacets>) => void;
  counts: EventFacetCounts;
  countsPending?: boolean;
};

export function EventsLeftRail({
  category,
  onCategoryChange,
  facets,
  onFacetsChange,
  counts,
  countsPending = false,
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
        counts={counts.categories}
        countsPending={countsPending}
      />

      <p className="mt-6 px-3 pb-2 text-[13px] font-medium text-muted">Only show</p>
      <EventFeedSwitches
        layout="rail"
        facets={facets}
        onFacetsChange={onFacetsChange}
        counts={counts}
        countsPending={countsPending}
      />

      <p className="mt-6 px-3 pb-2 text-[13px] font-medium text-muted">Hosted by</p>
      <EventHostGroupFilter
        layout="rail"
        hostGroup={facets.hostGroup}
        onHostGroupChange={(hostGroup) => onFacetsChange({ hostGroup })}
        counts={counts.hostGroups}
        countsPending={countsPending}
      />
    </div>
  );
}
