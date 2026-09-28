"use client";

import type { ReactNode } from "react";
import { CATEGORY_RAIL } from "@/lib/category-colors";
import {
  NO_FEED_FACETS,
  categoryLabel,
  dayWindowLabel,
  hostGroupLabel,
  type EventFeedFacets,
} from "./events-filters";
import type { EventFeedActiveFilters } from "./useEventFeedFilters";

type Props = {
  activeFilters: EventFeedActiveFilters;
  onClearCategory: () => void;
  onClearDayWindow: () => void;
  onClearQuery: () => void;
  onFacetsChange: (next: Partial<EventFeedFacets>) => void;
  onClearAll: () => void;
};

export function ActiveFilterChips({
  activeFilters,
  onClearCategory,
  onClearDayWindow,
  onClearQuery,
  onFacetsChange,
  onClearAll,
}: Props) {
  if (!activeFilters.hasAny) return null;

  const activeCategoryLabel = categoryLabel(activeFilters.category);
  const activeDayWindowLabel = dayWindowLabel(activeFilters.dayWindow);
  const activeHostGroupLabel = hostGroupLabel(activeFilters.hostGroup);

  return (
    <div
      role="group"
      aria-label="Active filters"
      className="mb-5 flex flex-wrap items-center gap-x-2 gap-y-1.5 border-b border-ink/10 pb-4"
    >
      {activeFilters.hasCategory && (
        <Chip
          ariaLabel={`Remove ${activeCategoryLabel} filter`}
          onClick={onClearCategory}
          dotClass={
            activeFilters.category === "all"
              ? undefined
              : CATEGORY_RAIL[activeFilters.category]
          }
        >
          {activeCategoryLabel}
        </Chip>
      )}
      {activeFilters.freeFood && (
        <Chip
          ariaLabel="Remove Free food filter"
          onClick={() => onFacetsChange({ freeFood: false })}
          dotClass="bg-tag-amber"
        >
          Free food
        </Chip>
      )}
      {activeFilters.deadlines && (
        <Chip
          ariaLabel="Remove Deadlines filter"
          onClick={() => onFacetsChange({ deadlines: false })}
          dotClass="bg-tag-coral"
        >
          Deadlines
        </Chip>
      )}
      {activeFilters.hasHostGroup && (
        <Chip
          ariaLabel={`Remove ${activeHostGroupLabel} filter`}
          onClick={() => onFacetsChange({ hostGroup: NO_FEED_FACETS.hostGroup })}
        >
          {activeHostGroupLabel}
        </Chip>
      )}
      {activeFilters.hasDayWindow && (
        <Chip
          ariaLabel={`Remove ${activeDayWindowLabel} filter`}
          onClick={onClearDayWindow}
        >
          {activeDayWindowLabel}
        </Chip>
      )}
      {activeFilters.hasQuery && (
        <Chip
          ariaLabel={`Clear search for ${activeFilters.query}`}
          onClick={onClearQuery}
        >
          “{activeFilters.query}”
        </Chip>
      )}
      <button
        type="button"
        onClick={onClearAll}
        className="interactive-focus ml-1 inline-flex min-h-11 items-center px-1 text-[13px] font-medium text-ink underline-offset-4 hover:underline"
      >
        Clear all
      </button>
    </div>
  );
}

type ChipProps = {
  ariaLabel: string;
  onClick: () => void;
  dotClass?: string;
  children: ReactNode;
};

function Chip({ ariaLabel, onClick, dotClass, children }: ChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      className="interactive-focus group inline-flex min-h-11 max-w-full items-center gap-1.5 rounded-full border border-ink/15 bg-surface px-3.5 text-[13px] text-ink transition-colors hover:border-ink"
    >
      {dotClass && (
        <span
          aria-hidden
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotClass}`}
        />
      )}
      <span className="min-w-0 max-w-[20ch] truncate">{children}</span>
      <svg
        aria-hidden
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="h-3.5 w-3.5 shrink-0 text-muted transition-colors group-hover:text-ink"
      >
        <path d="M6 6l12 12M6 18 18 6" />
      </svg>
    </button>
  );
}
