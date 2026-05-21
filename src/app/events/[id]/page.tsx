import type { Metadata } from "next";
import Image from "next/image";
import { notFound } from "next/navigation";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { getEventById } from "@/lib/events";
import { formatDay, formatTimeRange, relativeDay } from "@/lib/dates";
import { calendarHref } from "@/lib/event-actions";
import { ShareButton } from "@/components/events/ShareButton";
import { EventBackButton } from "@/components/events/EventBackButton";
import { TrackedAnchor } from "@/components/events/TrackedAnchor";
import { SITE_NAME, SITE_PREVIEW_IMAGE, absoluteUrl } from "@/lib/seo";
import { normalizeHttpUrl } from "@/lib/event-validation";
import type { CampusEvent } from "@/types/event";

export const dynamic = "force-dynamic";

const SOURCE_LABELS: Record<CampusEvent["source"], string> = {
  instagram: "Instagram",
  highlander_link: "Highlander Link",
  campus_website: "UCR Events",
  club_website: "Club site",
  manual: "Manual",
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const event = await getEventById(id);
  if (!event) return { title: "Event not found · Highlander Hub" };
  const title = event.title;
  const description = event.description.slice(0, 160);
  const url = `/events/${event.id}`;
  const image = event.imageUrl ?? SITE_PREVIEW_IMAGE;

  return {
    title,
    description,
    alternates: {
      canonical: url,
    },
    openGraph: {
      type: "article",
      siteName: SITE_NAME,
      title,
      description,
      url,
      images: [
        {
          url: image,
          alt: `${event.title} event preview`,
        },
      ],
    },
    twitter: {
      card: event.imageUrl ? "summary_large_image" : "summary",
      title,
      description,
      images: [absoluteUrl(image)],
    },
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

  const safeRsvpUrl = normalizeHttpUrl(event.rsvpUrl);
  const safeSourceUrl = normalizeHttpUrl(event.sourceUrl);
  const primaryUrl = safeRsvpUrl ?? safeSourceUrl;
  const primaryKind = safeRsvpUrl ? "rsvp" : "view_source";

  return (
    <main className="relative min-h-screen bg-canvas pb-28 md:pb-0">
      <Masthead />

      {/* Atmospheric backdrop: the flyer's mood color bleeds in, blurred low,
          then fades into canvas. Makes low-quality flyers feel intentional. */}
      {event.imageUrl && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-[58vh] overflow-hidden sm:h-[52vh]"
        >
          <Image
            src={event.imageUrl}
            alt=""
            fill
            sizes="100vw"
            className="scale-125 object-cover opacity-55 blur-3xl"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-canvas/30 via-canvas/65 to-canvas" />
        </div>
      )}

      <div className="relative mx-auto max-w-3xl px-4 pb-16 pt-6 sm:px-6">
        <EventBackButton />

        <article className="mt-8">
          {event.imageUrl && (
            <div className="mb-10 w-full max-w-[18rem]">
              <div className="relative aspect-[4/5] w-full overflow-hidden rounded-xl border border-white/50 bg-surface shadow-cardHover">
                <Image
                  src={event.imageUrl}
                  alt={`Flyer for ${event.title}`}
                  fill
                  sizes="(max-width: 640px) 70vw, 18rem"
                  className="object-cover"
                  priority
                />
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <CategoryBadge category={event.category} />
            {event.isFree && (
              <span className="inline-flex items-center rounded-full bg-leaf/10 px-2.5 py-0.5 text-[11px] font-medium text-[#1f6f4e]">
                Free
              </span>
            )}
            {event.rsvpRequired && (
              <span className="inline-flex items-center rounded-full border border-ink/15 px-2.5 py-0.5 text-[11px] font-medium text-muted">
                RSVP req.
              </span>
            )}
            <span className="ml-auto text-[13px] text-muted">
              {SOURCE_LABELS[event.source]}
            </span>
          </div>

          <h1 className="mt-5 font-display text-[32px] font-semibold leading-[1.08] tracking-[-0.025em] text-ink sm:text-[44px]">
            {event.title}
          </h1>

          <p className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="font-display text-xl font-semibold text-ink">
              {formatDay(event.startsAt)}
            </span>
            <span className="text-[13px] text-muted">
              {relativeDay(event.startsAt)}
            </span>
            <span className="text-ink/30">·</span>
            <span className="text-ink">
              {formatTimeRange(event.startsAt, event.endsAt)}
            </span>
          </p>

          <div className="mt-10 h-px w-full bg-ink/10" />

          <p className="mt-10 max-w-prose whitespace-pre-line text-[16px] leading-relaxed text-ink/80">
            {event.description}
          </p>

          <dl className="mt-12 grid grid-cols-1 gap-y-6 gap-x-12 sm:grid-cols-2">
            <div>
              <dt className="text-[13px] text-muted">Where</dt>
              <dd className="mt-1 text-ink">{event.location}</dd>
            </div>
            <div>
              <dt className="text-[13px] text-muted">Host</dt>
              <dd className="mt-1 text-ink">
                {event.host}
                {event.hostHandle && (
                  <span className="block text-xs text-muted">
                    {event.hostHandle}
                  </span>
                )}
              </dd>
            </div>
          </dl>

          {event.tags.length > 0 && (
            <div className="mt-8 flex flex-wrap gap-x-3 gap-y-1 text-[13px] text-muted">
              {event.tags.map((t) => (
                <span key={t}>#{t.replace(/\s+/g, "")}</span>
              ))}
            </div>
          )}

          {/* Desktop CTAs */}
          <div className="mt-12 hidden flex-wrap items-center gap-x-5 gap-y-3 border-t border-ink/10 pt-8 md:flex">
            {primaryUrl && (
              <TrackedAnchor
                event="primary"
                ctaKind={primaryKind}
                eventId={event.id}
                surface="desktop"
                href={primaryUrl}
                className="interactive-focus inline-flex min-h-12 items-center gap-2 rounded-lg bg-ink px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-85"
              >
                {safeRsvpUrl ? "RSVP" : "View source"}
                <span aria-hidden>↗</span>
              </TrackedAnchor>
            )}
            <TrackedAnchor
              event="calendar"
              eventId={event.id}
              surface="desktop"
              href={calendarHref(event)}
              className="interactive-focus text-sm font-medium text-ink underline-offset-4 hover:underline"
            >
              Add to calendar
            </TrackedAnchor>
            <ShareButton event={event} variant="text" />
          </div>
        </article>
      </div>

      {/* Mobile sticky action bar */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-ink/10 bg-canvas/95 px-4 py-3 backdrop-blur md:hidden">
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          {primaryUrl ? (
            <TrackedAnchor
              event="primary"
              ctaKind={primaryKind}
              eventId={event.id}
              surface="mobile"
              href={primaryUrl}
              className="interactive-focus flex-1 inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-ink px-4 py-3 text-sm font-medium text-white"
            >
              {safeRsvpUrl ? "RSVP" : "View source"}
              <span aria-hidden>↗</span>
            </TrackedAnchor>
          ) : null}
          <TrackedAnchor
            event="calendar"
            eventId={event.id}
            surface="mobile"
            href={calendarHref(event)}
            ariaLabel="Add to calendar"
            className="interactive-focus inline-flex min-h-12 min-w-12 items-center justify-center rounded-lg border border-ink/15 text-ink"
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
          </TrackedAnchor>
          <ShareButton event={event} variant="icon" />
        </div>
      </div>

      <Footer />
    </main>
  );
}
