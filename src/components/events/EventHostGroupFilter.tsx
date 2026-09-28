"use client";

import { HOST_GROUPS, type HostGroupValue } from "@/lib/host-groups";
import {
  EventFilterRow,
  FILTER_GROUP_CLASS,
  type FilterLayout,
} from "./EventFilterRow";

type EventHostGroupFilterProps = {
  layout: FilterLayout;
  hostGroup: HostGroupValue;
  onHostGroupChange: (next: HostGroupValue) => void;
  counts: Map<HostGroupValue, number>;
  countsPending?: boolean;
};

/**
 * Hosted by: who runs the event, from the account directory. At most one
 * group; choosing the selected one again clears it. Hosts are not a category,
 * so the selection is the neutral fill (DESIGN.md, The One Selected State).
 */
export function EventHostGroupFilter({
  layout,
  hostGroup,
  onHostGroupChange,
  counts,
  countsPending = false,
}: EventHostGroupFilterProps) {
  return (
    <div
      className={FILTER_GROUP_CLASS[layout]}
      role="group"
      aria-label="Filter events by host"
    >
      {HOST_GROUPS.map((group) => {
        const active = hostGroup === group.value;
        return (
          <EventFilterRow
            key={group.value}
            id={group.value}
            layout={layout}
            pressed={active}
            selectedClass="bg-ink/[0.06] text-ink"
            onClick={() => onHostGroupChange(active ? "all" : group.value)}
            count={counts.get(group.value) ?? 0}
            countsPending={countsPending}
          >
            {group.label}
          </EventFilterRow>
        );
      })}
    </div>
  );
}
