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

function calendarDate(value: string) {
  return new Date(value)
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\.\d{3}Z$/, "Z");
}

function addHours(value: string, hours: number) {
  return new Date(
    new Date(value).getTime() + hours * 60 * 60 * 1000
  ).toISOString();
}

function calendarHref(event: CampusEvent) {
  const end = event.endsAt ?? addHours(event.startsAt, 1);
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: event.title,
    dates: `${calendarDate(event.startsAt)}/${calendarDate(end)}`,
    details: event.description,
    location: event.location,
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

function shareHref(event: CampusEvent) {
  const url = event.rsvpUrl ?? event.sourceUrl;
  const body = [
    event.title,
    formatTimeRange(event.startsAt, event.endsAt),
    event.location,
    url,
  ]
    .filter(Boolean)
    .join("\n");
  return `mailto:?subject=${encodeURIComponent(
    event.title
  )}&body=${encodeURIComponent(body)}`;
}

function startDateParts(value: string) {
  const d = new Date(value);
  return {
    day: String(d.getDate()).padStart(2, "0"),
    month: d
      .toLocaleString("en-US", { month: "short" })
      .toUpperCase(),
  };
}

export function EventCard({ event }: { event: CampusEvent }) {
  const primaryUrl = event.rsvpUrl ?? event.sourceUrl;
  const { day, month } = startDateParts(event.startsAt);

  return (
    <article className="card-hover group relative flex h-full">
      <span
        aria-hidden
        className={`w-1 shrink-0 ${RAIL_COLORS[event.category]}`}
      />
      <div className="flex flex-1 flex-col border border-l-0 border-ink/15 bg-canvas">
        {/* Date strip */}
        <div className="flex items-center justify-between gap-3 border-b border-ink/10 px-5 py-3">
          <div className="flex items-baseline gap-2">
            <span className="font-display text-2xl font-semibold leading-none tracking-[-0.04em] text-ink">
              {day}
            </span>
            <span className="font-mono text-[11px] tracking-[0.16em] text-muted">
              {month}
            </span>
            <span className="font-mono text-[11px] tracking-[0.06em] text-muted">
              · {relativeDay(event.startsAt)}
            </span>
          </div>
          <span className="font-mono text-[11px] tracking-[0.06em] text-muted">
            {formatTimeRange(event.startsAt, event.endsAt)}
          </span>
        </div>

        <div className="flex flex-1 flex-col gap-3 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <CategoryBadge category={event.category} />
            {event.isFree && (
              <span className="inline-flex items-center bg-leaf/10 px-2 py-0.5 text-[11px] font-medium text-[#1f6f4e]">
                Free
              </span>
            )}
            {event.rsvpRequired && (
              <span className="inline-flex items-center border border-ink/15 bg-canvas px-2 py-0.5 text-[11px] font-medium text-muted">
                RSVP req.
              </span>
            )}
            <span className="ml-auto font-mono text-[11px] tracking-[0.06em] text-muted">
              {SOURCE_LABELS[event.source]}
            </span>
          </div>

          <h3 className="font-display text-[22px] font-semibold leading-[1.15] tracking-[-0.02em] text-ink">
            {event.title}
          </h3>

          <p className="text-sm leading-relaxed text-ink/75 line-clamp-3">
            {event.description}
          </p>

          <dl className="mt-2 grid grid-cols-2 gap-3 border-t border-ink/10 pt-3 text-sm">
            <div>
              <dt className="text-xs text-muted mb-0.5">Where</dt>
              <dd className="text-ink">{event.location}</dd>
            </div>
            <div className="text-right">
              <dt className="text-xs text-muted mb-0.5">Host</dt>
              <dd className="text-ink">
                {event.host}
                {event.hostHandle && (
                  <span className="block font-mono text-xs text-muted">
                    {event.hostHandle}
                  </span>
                )}
              </dd>
            </div>
          </dl>

          {event.tags.length > 0 && (
            <div className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-[11px] text-muted">
              {event.tags.map((t) => (
                <span key={t}>#{t.replace(/\s+/g, "")}</span>
              ))}
            </div>
          )}

          <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-2 pt-2">
            {primaryUrl && (
              <a
                href={primaryUrl}
                target="_blank"
                rel="noreferrer"
                aria-label={`${event.rsvpUrl ? "RSVP for" : "View source for"} ${event.title}`}
                className="interactive-focus inline-flex items-center gap-2 bg-ink px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-85"
              >
                {event.rsvpUrl ? "RSVP" : "View source"}
                <span aria-hidden>↗</span>
              </a>
            )}
            <a
              href={calendarHref(event)}
              target="_blank"
              rel="noreferrer"
              aria-label={`Add ${event.title} to calendar`}
              className="interactive-focus text-sm font-medium text-ink underline-offset-4 hover:underline"
            >
              Add to calendar
            </a>
            <a
              href={shareHref(event)}
              aria-label={`Share ${event.title}`}
              className="interactive-focus text-sm font-medium text-ink underline-offset-4 hover:underline"
            >
              Share
            </a>
          </div>
        </div>
      </div>
    </article>
  );
}
