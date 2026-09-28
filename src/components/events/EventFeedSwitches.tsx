"use client";

import { DEADLINE_PILL, FREE_FOOD_PILL } from "@/lib/category-colors";
import type { EventFeedFacets } from "./events-filters";
import {
  EventFilterRow,
  FILTER_GROUP_CLASS,
  type FilterLayout,
} from "./EventFilterRow";

type SwitchKey = "freeFood" | "deadlines";

const SWITCHES: { key: SwitchKey; label: string; pill: { highlight: string; text: string } }[] = [
  { key: "freeFood", label: "Free food", pill: FREE_FOOD_PILL },
  { key: "deadlines", label: "Deadlines", pill: DEADLINE_PILL },
];

type EventFeedSwitchesProps = {
  layout: FilterLayout;
  facets: EventFeedFacets;
  onFacetsChange: (next: Partial<EventFeedFacets>) => void;
  counts: Record<SwitchKey, number>;
  countsPending?: boolean;
};

/**
 * "Only show" switches. Unlike a topic, each narrows whatever else is chosen,
 * so Hang out + Free food is one question. The check box says so, and each
 * pressed row wears its tag's wash (amber food, coral deadline).
 */
export function EventFeedSwitches({
  layout,
  facets,
  onFacetsChange,
  counts,
  countsPending = false,
}: EventFeedSwitchesProps) {
  return (
    <div className={FILTER_GROUP_CLASS[layout]} role="group" aria-label="Only show">
      {SWITCHES.map(({ key, label, pill }) => {
        const on = facets[key];
        return (
          <EventFilterRow
            key={key}
            id={key}
            layout={layout}
            pressed={on}
            selectedClass={`${pill.highlight} ${pill.text}`}
            onClick={() => onFacetsChange({ [key]: !on })}
            count={counts[key]}
            countsPending={countsPending}
            leading={
              <span
                aria-hidden
                className={`mr-2.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-[5px] ${
                  on ? "bg-current" : "ring-1 ring-inset ring-ink/30"
                }`}
              >
                {on && (
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-3 w-3 text-canvas"
                  >
                    <path d="M5 12.5l4.5 4.5L19 7.5" />
                  </svg>
                )}
              </span>
            }
          >
            {label}
          </EventFilterRow>
        );
      })}
    </div>
  );
}
