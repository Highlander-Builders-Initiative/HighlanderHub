import type { ReactNode } from "react";
import { formatTimeParts } from "@/lib/dates";
import { CATEGORY_RAIL } from "@/lib/category-colors";
import { isDeadlineKind } from "@/lib/events/content-kind";
import type { CampusEvent } from "@/types/event";

type EventListRowTimeColumnProps = {
  startsAt: string;
  category: CampusEvent["category"];
  contentKind?: CampusEvent["contentKind"];
  compact?: boolean;
  /** Optional slot above the time (e.g. admin feed index). */
  prefix?: ReactNode;
};

/**
 * Shared time column for public EventCard and admin live-event rows. Deadlines
 * carry a "Due" eyebrow so the time reads as a cutoff rather than a start.
 */
export function EventListRowTimeColumn({
  startsAt,
  category,
  contentKind,
  compact = false,
  prefix,
}: EventListRowTimeColumnProps) {
  const { time, period } = formatTimeParts(startsAt);
  const rail = CATEGORY_RAIL[category];
  const isDeadline = isDeadlineKind(contentKind);

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
      {isDeadline && (
        <span
          className={`font-mono font-semibold uppercase text-deep-coral ${
            compact
              ? "mb-0.5 text-[8px] tracking-[0.1em]"
              : "mb-1 text-[9px] tracking-[0.14em]"
          }`}
        >
          Due
        </span>
      )}
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
