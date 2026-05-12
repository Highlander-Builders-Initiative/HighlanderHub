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

const CATEGORY_MEDIA: Record<
  CampusEvent["category"],
  { label: string; cls: string }
> = {
  club: { label: "Club meet", cls: "from-highlander/20 to-sky/10 text-highlander" },
  academic: { label: "Talk", cls: "from-emerald-100 to-leaf/10 text-[#1f6f4e]" },
  social: { label: "Social", cls: "from-rose-100 to-coral/10 text-[#b33a30]" },
  career: { label: "Career", cls: "from-zinc-100 to-ink/10 text-ink" },
  sports: { label: "Game day", cls: "from-blue-100 to-sky/10 text-[#1d5fbf]" },
  arts: { label: "Arts", cls: "from-rose-100 to-coral/10 text-[#b33a30]" },
  community: { label: "Local", cls: "from-emerald-100 to-leaf/10 text-[#1f6f4e]" },
  free_food: { label: "Free food", cls: "from-yellow-100 to-gold/20 text-[#8a6300]" },
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

  return `mailto:?subject=${encodeURIComponent(event.title)}&body=${encodeURIComponent(body)}`;
}

export function EventCard({ event }: { event: CampusEvent }) {
  const media = CATEGORY_MEDIA[event.category];
  const primaryUrl = event.rsvpUrl ?? event.sourceUrl;

  return (
    <article className="card-hover group relative flex h-full flex-col overflow-hidden rounded-lg border border-line bg-canvas shadow-card">
      {event.imageUrl ? (
        <img
          src={event.imageUrl}
          alt={`${event.title} preview`}
          loading="lazy"
          className="aspect-[16/9] w-full object-cover"
        />
      ) : (
        <div
          aria-hidden="true"
          className={`flex aspect-[16/9] items-end justify-between bg-gradient-to-br p-4 ${media.cls}`}
        >
          <span className="rounded-full bg-white/80 px-3 py-1 text-xs font-semibold shadow-sm">
            {media.label}
          </span>
          <span className="font-display text-3xl font-bold opacity-20">
            {relativeDay(event.startsAt)}
          </span>
        </div>
      )}

      <div className="flex flex-1 flex-col gap-3 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-wrap gap-1.5">
            <CategoryBadge category={event.category} />
            {event.isFree && (
              <span className="inline-flex items-center rounded-full bg-leaf/10 text-[#1f6f4e] px-2.5 py-0.5 text-xs font-medium">
                Free
              </span>
            )}
            {event.rsvpRequired && (
              <span className="inline-flex items-center rounded-full bg-surface text-muted px-2.5 py-0.5 text-xs font-medium border border-line">
                RSVP
              </span>
            )}
          </div>
          <span className="shrink-0 text-xs text-muted">
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

        <h3 className="font-display text-xl font-semibold leading-snug text-ink">
          {event.title}
        </h3>

        <p className="text-sm leading-relaxed text-muted line-clamp-3">
          {event.description}
        </p>

        <div className="mt-auto pt-3 border-t border-line flex items-end justify-between gap-3 flex-wrap text-sm">
          <div className="flex flex-col">
            <span className="text-xs uppercase tracking-wide text-muted">
              Where
            </span>
            <span className="text-ink">{event.location}</span>
          </div>
          <div className="flex flex-col text-right">
            <span className="text-xs uppercase tracking-wide text-muted">
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
              <span key={t} className="text-xs text-muted">
                #{t.replace(/\s+/g, "")}
              </span>
            ))}
          </div>
        )}

        <div className="flex flex-wrap gap-2 pt-1">
          {primaryUrl && (
            <a
              href={primaryUrl}
              target="_blank"
              rel="noreferrer"
              aria-label={`${event.rsvpUrl ? "RSVP for" : "View source for"} ${event.title}`}
              className="interactive-focus inline-flex min-h-11 items-center gap-2 rounded-full bg-highlander px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-ink"
            >
              {event.rsvpUrl ? "RSVP" : "View source"}
              <span aria-hidden>→</span>
            </a>
          )}
          <a
            href={calendarHref(event)}
            target="_blank"
            rel="noreferrer"
            aria-label={`Add ${event.title} to calendar`}
            className="interactive-focus inline-flex min-h-11 items-center rounded-full border border-line px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-highlander hover:text-highlander"
          >
            Add to calendar
          </a>
          <a
            href={shareHref(event)}
            aria-label={`Share ${event.title}`}
            className="interactive-focus inline-flex min-h-11 items-center rounded-full border border-line px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-highlander hover:text-highlander"
          >
            Share
          </a>
        </div>
      </div>
    </article>
  );
}
