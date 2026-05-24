import Link from "next/link";
import { EVENT_CATEGORY_LABELS, type CampusEvent } from "@/types/event";
import { formatTimeParts, relativeDay } from "@/lib/dates";
import { eventListLinkLabel } from "@/lib/events/a11y";
import { CATEGORY_RAIL } from "@/lib/category-colors";

function shortCategory(category: CampusEvent["category"]): string {
  return EVENT_CATEGORY_LABELS[category].split(" / ")[0];
}

export function HeroLeadEvent({ event }: { event: CampusEvent }) {
  const { time, period } = formatTimeParts(event.startsAt);
  const day = relativeDay(event.startsAt);

  return (
    <Link
      href={`/events/${event.id}`}
      aria-label={eventListLinkLabel(event)}
      className="interactive-focus group block"
    >
      <p className="text-[13px] text-muted">Coming up</p>

      <p className="mt-3 font-mono text-[20px] font-medium leading-none tracking-[0.01em] text-ink">
        <span>{day}</span>
        <span aria-hidden className="mx-2 text-ink/30">
          ·
        </span>
        <span className="tabular-nums">{time}</span>
        {period && (
          <span className="ml-1 text-[15px] text-muted">
            {period.toLowerCase()}
          </span>
        )}
      </p>

      <div className="mt-5 flex items-start gap-2">
        <span
          aria-hidden
          className={`mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full ${CATEGORY_RAIL[event.category]}`}
        />
        <h2 className="font-display text-[24px] font-semibold leading-[1.15] tracking-[-0.02em] text-ink line-clamp-2 group-hover:underline group-hover:decoration-ink/40 group-hover:underline-offset-4 lg:text-[26px]">
          {event.title}
        </h2>
      </div>

      <div className="mt-3 flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-1 text-[13px] text-muted">
        <span className="min-w-0 truncate">{event.location}</span>
        <span aria-hidden className="shrink-0 text-ink/20">
          ·
        </span>
        <span className="min-w-0 truncate">{event.host}</span>
        <span aria-hidden className="shrink-0 text-ink/20">
          ·
        </span>
        <span className="shrink-0">{shortCategory(event.category)}</span>
        {event.isFree && (
          <span className="ml-0.5 inline-flex items-center rounded-full bg-leaf/10 px-2 py-0.5 text-[11px] font-medium text-deep-leaf">
            Free
          </span>
        )}
      </div>
    </Link>
  );
}
