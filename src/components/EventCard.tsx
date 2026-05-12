import type { CampusEvent } from "@/types/event";
import { formatTimeRange, relativeDay } from "@/lib/dates";
import { CategoryBadge } from "./CategoryBadge";

const SOURCE_LABELS: Record<CampusEvent["source"], string> = {
  instagram: "Instagram",
  highlander_link: "Highlander Link",
  campus_website: "UCR Events",
  club_website: "Club site",
  manual: "Manual",
};

export function EventCard({ event }: { event: CampusEvent }) {
  return (
    <article className="card-hover group relative flex h-full flex-col gap-3 rounded-2xl border border-line bg-canvas p-5 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          <CategoryBadge category={event.category} />
          {event.isFree && (
            <span className="inline-flex items-center rounded-full bg-leaf/10 text-leaf px-2.5 py-0.5 text-[11px] font-medium">
              Free
            </span>
          )}
          {event.rsvpRequired && (
            <span className="inline-flex items-center rounded-full bg-surface text-muted px-2.5 py-0.5 text-[11px] font-medium border border-line">
              RSVP
            </span>
          )}
        </div>
        <span className="shrink-0 text-[11px] text-muted">
          {SOURCE_LABELS[event.source]}
        </span>
      </div>

      <div className="flex items-baseline gap-2 text-sm">
        <span className="font-semibold text-ink">
          {relativeDay(event.startsAt)}
        </span>
        <span className="text-line">·</span>
        <span className="text-muted">
          {formatTimeRange(event.startsAt, event.endsAt)}
        </span>
      </div>

      <h3 className="font-display text-xl font-semibold leading-snug tracking-tight text-ink">
        {event.title}
      </h3>

      <p className="text-sm leading-relaxed text-muted line-clamp-3">
        {event.description}
      </p>

      <div className="mt-auto pt-3 border-t border-line flex items-end justify-between gap-3 flex-wrap text-sm">
        <div className="flex flex-col">
          <span className="text-[11px] uppercase tracking-wide text-muted">
            Where
          </span>
          <span className="text-ink">{event.location}</span>
        </div>
        <div className="flex flex-col text-right">
          <span className="text-[11px] uppercase tracking-wide text-muted">
            Host
          </span>
          <span className="text-ink">
            {event.host}
            {event.hostHandle && (
              <span className="block font-mono text-xs text-muted">
                {event.hostHandle}
              </span>
            )}
          </span>
        </div>
      </div>

      {event.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {event.tags.map((t) => (
            <span key={t} className="text-[11px] text-muted">
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
          className="inline-flex w-fit items-center gap-1 text-sm font-medium text-highlander hover:underline"
        >
          {event.rsvpUrl ? "RSVP" : "View source"}
          <span aria-hidden>→</span>
        </a>
      )}
    </article>
  );
}
