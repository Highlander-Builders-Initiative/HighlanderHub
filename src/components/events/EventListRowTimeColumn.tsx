import type { ReactNode } from "react";
import { formatTimeParts } from "@/lib/dates";
import { CATEGORY_RAIL } from "@/lib/category-colors";
import type { CampusEvent } from "@/types/event";

type EventListRowTimeColumnProps = {
  startsAt: string;
  category: CampusEvent["category"];
  compact?: boolean;
  /** Optional slot above the time (e.g. admin feed index). */
  prefix?: ReactNode;
};

/**
 * Shared time column for public EventCard and admin live-event rows.
 */
export function EventListRowTimeColumn({
  startsAt,
  category,
  compact = false,
  prefix,
}: EventListRowTimeColumnProps) {
  const { time, period } = formatTimeParts(startsAt);
  const rail = CATEGORY_RAIL[category];

  return (
    <div
      className={`relative flex shrink-0 flex-col items-center justify-center px-2 ${
        compact ? "w-[52px]" : "w-16 sm:w-[68px]"
      }`}
    >
      <span
        aria-hidden
        className={`pointer-events-none absolute bottom-0 right-0 top-0 w-[2px] ${rail}`}
      />
      {prefix}
      <span
        className={`font-mono font-medium leading-none text-ink tabular-nums ${
          compact ? "text-base" : "text-[22px]"
        }`}
      >
        {time}
      </span>
      {period && (
        <span
          className={`mt-1.5 font-mono font-medium uppercase text-muted ${
            compact ? "text-[9px] tracking-[0.1em]" : "text-[10px] tracking-[0.14em]"
          }`}
        >
          {period}
        </span>
      )}
    </div>
  );
}
