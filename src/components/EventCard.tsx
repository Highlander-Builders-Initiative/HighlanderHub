import Link from "next/link";
import type { CampusEvent } from "@/types/event";
import { formatTime, relativeDay } from "@/lib/dates";
import { CategoryBadge } from "./CategoryBadge";

const RAIL_COLORS: Record<CampusEvent["category"], string> = {
  club: "bg-highlander",
  academic: "bg-leaf",
  social: "bg-coral",
  career: "bg-ink",
  sports: "bg-sky",
  arts: "bg-coral",
  community: "bg-leaf",
  free_food: "bg-gold",
};

export function EventCard({ event }: { event: CampusEvent }) {
  return (
    <Link
      href={`/events/${event.id}`}
      aria-label={`${event.title} — ${relativeDay(event.startsAt)} at ${formatTime(event.startsAt)}`}
      className="card-hover group relative flex h-full w-full min-w-0"
    >
      <span
        aria-hidden
        className={`w-1 shrink-0 ${RAIL_COLORS[event.category]}`}
      />
      <div className="flex min-w-0 flex-1 items-stretch border border-l-0 border-ink/15 bg-canvas">
        <div className="flex min-w-0 flex-1 flex-col justify-center gap-1 px-4 py-3 sm:px-5 sm:py-4">
          <div className="flex min-w-0 items-center gap-2 font-mono text-[11px] tracking-[0.06em] text-muted">
            <span className="shrink-0">{formatTime(event.startsAt)}</span>
            <span className="shrink-0 text-ink/20">·</span>
            <span className="min-w-0 truncate">{event.location}</span>
          </div>

          <h3 className="font-display text-[17px] font-semibold leading-[1.2] tracking-[-0.015em] text-ink line-clamp-2 break-words sm:text-[18px]">
            {event.title}
          </h3>

          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
            <span className="min-w-0 max-w-full truncate text-[13px] text-muted">
              {event.host}
            </span>
            <CategoryBadge category={event.category} />
            {event.isFree && (
              <span className="inline-flex items-center bg-leaf/10 px-1.5 py-0.5 text-[11px] font-medium text-[#1f6f4e]">
                Free
              </span>
            )}
          </div>
        </div>

        <div
          aria-hidden
          className="flex shrink-0 items-center pr-3 text-muted transition-colors group-hover:text-ink sm:pr-4"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-4 w-4"
          >
            <path d="m9 18 6-6-6-6" />
          </svg>
        </div>
      </div>
    </Link>
  );
}
