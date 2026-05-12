import type { CampusEvent } from "@/types/event";
import { formatTimeRange, relativeDay } from "@/lib/dates";
import { CategoryBadge } from "./CategoryBadge";

const SOURCE_LABELS: Record<CampusEvent["source"], string> = {
  instagram: "via Instagram",
  highlander_link: "via Highlander Link",
  campus_website: "via UCR Events",
  club_website: "via Club Site",
  manual: "Added manually",
};

export function EventCard({ event }: { event: CampusEvent }) {
  return (
    <article className="lift bg-bone border border-ink p-5 flex flex-col gap-3 h-full">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <CategoryBadge category={event.category} />
          {event.isFree && (
            <span className="font-mono text-[10px] uppercase tracking-widest px-2 py-1 border border-ink">
              Free
            </span>
          )}
          {event.rsvpRequired && (
            <span className="font-mono text-[10px] uppercase tracking-widest px-2 py-1 border border-ink">
              RSVP
            </span>
          )}
        </div>
        <div className="text-right font-mono text-[10px] uppercase tracking-widest text-ink/60 shrink-0">
          {SOURCE_LABELS[event.source]}
        </div>
      </div>

      <div className="flex items-baseline gap-3 font-mono text-xs uppercase tracking-widest text-ink/70">
        <span className="font-bold text-ink">{relativeDay(event.startsAt)}</span>
        <span>·</span>
        <span>{formatTimeRange(event.startsAt, event.endsAt)}</span>
      </div>

      <h3 className="font-display text-2xl leading-tight font-medium">
        {event.title}
      </h3>

      <p className="font-body text-base leading-snug text-ink/80">
        {event.description}
      </p>

      <div className="mt-auto pt-3 border-t border-ink/20 flex items-end justify-between gap-3 flex-wrap">
        <div className="flex flex-col">
          <span className="font-mono text-[10px] uppercase tracking-widest text-ink/60">
            Where
          </span>
          <span className="font-body italic">{event.location}</span>
        </div>
        <div className="flex flex-col text-right">
          <span className="font-mono text-[10px] uppercase tracking-widest text-ink/60">
            Hosted by
          </span>
          <span className="font-body italic">
            {event.host}
            {event.hostHandle && (
              <span className="font-mono not-italic text-sm text-ink/60">
                {" "}
                {event.hostHandle}
              </span>
            )}
          </span>
        </div>
      </div>

      {event.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {event.tags.map((t) => (
            <span
              key={t}
              className="font-mono text-[10px] uppercase tracking-wider text-ink/50"
            >
              #{t.replace(/\s+/g, "")}
            </span>
          ))}
        </div>
      )}

      {(event.rsvpUrl || event.sourceUrl) && (
        <a
          href={event.rsvpUrl ?? event.sourceUrl}
          target="_blank"
          rel="noreferrer"
          className="font-mono text-xs uppercase tracking-widest link-underline w-fit"
        >
          {event.rsvpUrl ? "RSVP →" : "View source →"}
        </a>
      )}
    </article>
  );
}
