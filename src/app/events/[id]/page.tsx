import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Masthead } from "@/components/Masthead";
import { Footer } from "@/components/Footer";
import { CategoryBadge } from "@/components/CategoryBadge";
import { getEventById } from "@/lib/events";
import { formatDay, formatTimeRange, relativeDay } from "@/lib/dates";
import { calendarHref, shareHref } from "@/lib/event-actions";
import type { CampusEvent } from "@/types/event";

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

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const event = await getEventById(id);
  if (!event) return { title: "Event not found · Highlander Hub" };
  return {
    title: `${event.title} · Highlander Hub`,
    description: event.description.slice(0, 160),
  };
}

export default async function EventDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const event = await getEventById(id);
  if (!event) notFound();

  const primaryUrl = event.rsvpUrl ?? event.sourceUrl;

  return (
    <main className="min-h-screen bg-canvas pb-28 md:pb-0">
      <Masthead />

      <div className="mx-auto max-w-3xl px-4 pb-16 pt-6 sm:px-6">
        <Link
          href="/events"
          className="interactive-focus inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink"
        >
          <span aria-hidden>←</span> All events
        </Link>

        <article className="mt-6 flex">
          <span
            aria-hidden
            className={`w-1 shrink-0 ${RAIL_COLORS[event.category]}`}
          />
          <div className="flex-1 border border-l-0 border-ink/15 bg-canvas">
            <div className="border-b border-ink/10 px-5 py-4 sm:px-7">
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

              <h1 className="mt-4 font-display text-[30px] font-semibold leading-[1.1] tracking-[-0.025em] text-ink sm:text-[40px]">
                {event.title}
              </h1>

              <div className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
                <span className="font-display text-lg font-semibold text-ink">
                  {formatDay(event.startsAt)}
                </span>
                <span className="font-mono text-[11px] tracking-[0.06em] text-muted">
                  {relativeDay(event.startsAt)}
                </span>
                <span className="text-ink/30">·</span>
                <span className="text-ink">
                  {formatTimeRange(event.startsAt, event.endsAt)}
                </span>
              </div>
            </div>

            <div className="px-5 py-6 sm:px-7">
              <p className="whitespace-pre-line text-[15px] leading-relaxed text-ink/80">
                {event.description}
              </p>

              <dl className="mt-8 grid grid-cols-1 gap-5 border-t border-ink/10 pt-6 sm:grid-cols-2">
                <div>
                  <dt className="text-xs uppercase tracking-[0.08em] text-muted">
                    Where
                  </dt>
                  <dd className="mt-1 text-ink">{event.location}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-[0.08em] text-muted">
                    Host
                  </dt>
                  <dd className="mt-1 text-ink">
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
                <div className="mt-6 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[12px] text-muted">
                  {event.tags.map((t) => (
                    <span key={t}>#{t.replace(/\s+/g, "")}</span>
                  ))}
                </div>
              )}

              {/* Desktop CTAs */}
              <div className="mt-8 hidden flex-wrap items-center gap-x-5 gap-y-3 border-t border-ink/10 pt-6 md:flex">
                {primaryUrl && (
                  <a
                    href={primaryUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="interactive-focus inline-flex min-h-12 items-center gap-2 bg-ink px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-85"
                  >
                    {event.rsvpUrl ? "RSVP" : "View source"}
                    <span aria-hidden>↗</span>
                  </a>
                )}
                <a
                  href={calendarHref(event)}
                  target="_blank"
                  rel="noreferrer"
                  className="interactive-focus text-sm font-medium text-ink underline-offset-4 hover:underline"
                >
                  Add to calendar
                </a>
                <a
                  href={shareHref(event)}
                  className="interactive-focus text-sm font-medium text-ink underline-offset-4 hover:underline"
                >
                  Share
                </a>
              </div>
            </div>
          </div>
        </article>
      </div>

      {/* Mobile sticky action bar */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-ink/10 bg-canvas/95 px-4 py-3 backdrop-blur md:hidden">
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          {primaryUrl ? (
            <a
              href={primaryUrl}
              target="_blank"
              rel="noreferrer"
              className="interactive-focus flex-1 inline-flex min-h-12 items-center justify-center gap-2 bg-ink px-4 py-3 text-sm font-medium text-white"
            >
              {event.rsvpUrl ? "RSVP" : "View source"}
              <span aria-hidden>↗</span>
            </a>
          ) : null}
          <a
            href={calendarHref(event)}
            target="_blank"
            rel="noreferrer"
            aria-label="Add to calendar"
            className="interactive-focus inline-flex min-h-12 min-w-12 items-center justify-center border border-ink/15 text-ink"
          >
            <svg
              aria-hidden
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
            >
              <rect x="3" y="4" width="18" height="18" rx="0" />
              <path d="M16 2v4M8 2v4M3 10h18" />
            </svg>
          </a>
          <a
            href={shareHref(event)}
            aria-label="Share"
            className="interactive-focus inline-flex min-h-12 min-w-12 items-center justify-center border border-ink/15 text-ink"
          >
            <svg
              aria-hidden
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
            >
              <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
              <path d="M16 6l-4-4-4 4" />
              <path d="M12 2v13" />
            </svg>
          </a>
        </div>
      </div>

      <Footer />
    </main>
  );
}
