import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { getEventById } from "@/lib/events";
import {
  formatDateStamp,
  formatDay,
  formatTimeRange,
  relativeDay,
} from "@/lib/dates";
import { calendarHref } from "@/lib/events/actions";
import { ShareButton } from "@/components/events/ShareButton";
import { EventBackButton } from "@/components/events/EventBackButton";
import { EventFlyerImage } from "@/components/events/EventFlyerImage";
import { TrackedAnchor } from "@/components/events/TrackedAnchor";
import { SITE_NAME, SITE_PREVIEW_IMAGE, absoluteUrl } from "@/lib/seo";
import { normalizeHttpUrl } from "@/lib/events/validation";
import type { CampusEvent } from "@/types/event";

// Rendered per request: the no-store Supabase client (see lib/supabase.ts) bars
// static prerendering. getEventById reads through the Data Cache (see lib/events)
// so repeat views skip the round-trip; admin edits bust it via revalidateTag.
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
  const stamp = formatDateStamp(event.startsAt);
  const sourceLabel = SOURCE_LABELS[event.source];
  const hasImage = Boolean(event.imageUrl);
  const showHostedBy = Boolean(event.host || event.hostHandle);

  return (
    <main className="relative min-h-screen bg-canvas pb-28 md:pb-0">
      <Masthead />

      {/* Atmospheric backdrop: the flyer's mood color bleeds in, blurred low,
          then fades into canvas. Reduced height so it accents the two-column
          layout instead of dominating it. */}
      {event.imageUrl && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-[40vh] overflow-hidden sm:h-[36vh]"
        >
          <EventFlyerImage
            src={event.imageUrl}
            alt=""
            fill
            sizes="100vw"
            className="scale-125 object-cover opacity-45 blur-3xl"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-canvas/40 via-canvas/75 to-canvas" />
        </div>
      )}

      <div className="relative mx-auto max-w-5xl px-4 pb-16 pt-6 sm:px-6">
        <EventBackButton />

        <article className="mt-7 md:mt-10">
          {/* Header: pills + title sit full-bleed across both columns for
              editorial impact, regardless of whether the flyer rail renders. */}
          <header>
            <div className="flex flex-wrap items-center gap-2">
              <CategoryBadge category={event.category} />
              {event.isFree && (
                <span className="inline-flex items-center rounded-full bg-leaf/10 px-2.5 py-0.5 text-[12px] font-medium text-deep-leaf">
                  Free
                </span>
              )}
              {event.rsvpRequired && (
                <span className="inline-flex items-center rounded-full border border-ink/15 px-2.5 py-0.5 text-[12px] font-medium text-muted">
                  RSVP required
                </span>
              )}
            </div>

            <h1 className="mt-5 max-w-3xl font-display text-[34px] font-semibold leading-[1.05] tracking-[-0.025em] text-ink sm:text-[44px]">
              {event.title}
            </h1>
          </header>

          <div
            className={
              hasImage
                ? "mt-8 grid grid-cols-1 gap-10 md:mt-10 md:grid-cols-[minmax(0,18rem)_minmax(0,1fr)] md:gap-12 lg:grid-cols-[minmax(0,21rem)_minmax(0,1fr)] lg:gap-14"
                : "mt-8 max-w-3xl"
            }
          >
            {hasImage && (
              <aside className="order-2 space-y-6 md:order-1 md:sticky md:top-24 md:self-start">
                <div className="relative mx-auto w-full max-w-[18rem] overflow-hidden rounded-xl border border-ink/10 bg-surface shadow-card md:mx-0 md:max-w-none">
                  <div className="relative aspect-[4/5] w-full">
                    <EventFlyerImage
                      src={event.imageUrl!}
                      alt={`Flyer for ${event.title}`}
                      fill
                      sizes="(max-width: 768px) 80vw, (max-width: 1024px) 18rem, 21rem"
                      className="object-cover"
                      priority
                    />
                  </div>
                </div>

                <dl className="space-y-4 text-[14px]">
                  {showHostedBy && (
                    <>
                      <div>
                        <dt className="text-[12px] text-muted">Hosted by</dt>
                        <dd className="mt-1 font-medium text-ink">
                          {event.host}
                          {event.hostHandle && (
                            <span className="mt-0.5 block text-[13px] font-normal text-muted">
                              {event.hostHandle}
                            </span>
                          )}
                        </dd>
                      </div>
                      <div className="hairline" />
                    </>
                  )}
                  <div>
                    <dt className="text-[12px] text-muted">Source</dt>
                    <dd className="mt-1 text-ink">{sourceLabel}</dd>
                  </div>
                </dl>
              </aside>
            )}

            <div className="order-1 min-w-0 md:order-2">
              <section aria-label="When and where" className="space-y-3">
                <div className="flex items-center gap-4">
                  <div
                    aria-hidden
                    className="flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-lg border border-ink/15 bg-canvas"
                  >
                    <span className="text-[11px] text-muted">{stamp.month}</span>
                    <span className="mt-0.5 font-mono text-[20px] font-semibold leading-none tabular-nums text-ink">
                      {stamp.day}
                    </span>
                  </div>
                  <div className="min-w-0">
                    <div className="font-display text-[17px] font-semibold text-ink">
                      {formatDay(event.startsAt)}
                    </div>
                    <div className="mt-0.5 text-[14px] text-muted">
                      <span className="font-mono tabular-nums text-ink/85">
                        {formatTimeRange(event.startsAt, event.endsAt)}
                      </span>
                      <span aria-hidden className="mx-2 text-ink/25">
                        ·
                      </span>
                      <span>{relativeDay(event.startsAt)}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div
                    aria-hidden
                    className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg border border-ink/15 bg-canvas"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.75"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="h-[18px] w-[18px] text-muted"
                    >
                      <path d="M12 21s-7-7.5-7-12a7 7 0 1 1 14 0c0 4.5-7 12-7 12Z" />
                      <circle cx="12" cy="9" r="2.5" />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <div className="text-[15px] text-ink">{event.location}</div>
                  </div>
                </div>
              </section>

              {/* Registration card — desktop only; mobile is served by the
                  sticky bottom action bar. Hairline border, no fill, so it
                  groups the actions without nesting card-on-card. */}
              <section
                aria-label="Registration"
                className="mt-8 hidden rounded-xl border border-ink/15 bg-canvas p-5 md:block"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                  <div className="text-[13px] text-muted">
                    {primaryUrl
                      ? safeRsvpUrl
                        ? "Registration"
                        : "Event details"
                      : "Event details"}
                  </div>
                  {primaryUrl && (
                    <div className="text-[13px] text-muted">
                      via {sourceLabel}
                    </div>
                  )}
                </div>
                {!primaryUrl && (
                  <p className="mt-2 text-[14px] text-ink/75">
                    No external link is on file. Check with the host for the
                    latest info.
                  </p>
                )}
                <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-3">
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
              </section>

              <section aria-label="About" className="mt-10">
                <div className="hairline" />
                <h2 className="mt-7 font-display text-[20px] font-semibold tracking-[-0.015em] text-ink">
                  About
                </h2>
                <p className="mt-4 max-w-prose whitespace-pre-line text-[16px] leading-relaxed text-ink/80">
                  {event.description}
                </p>

                {event.tags.length > 0 && (
                  <div className="mt-6 flex flex-wrap gap-x-3 gap-y-1 text-[13px] text-muted">
                    {event.tags.map((t) => (
                      <span key={t}>#{t.replace(/\s+/g, "")}</span>
                    ))}
                  </div>
                )}
              </section>
            </div>
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
