import { CategoryBadge } from "@/components/ui/CategoryBadge";
import {
  formatDateStamp,
  formatDay,
  formatTimeRange,
  relativeDay,
} from "@/lib/dates";
import { EventCalendarMenu } from "@/components/events/EventCalendarMenu";
import { ShareButton } from "@/components/events/ShareButton";
import { EventBackButton } from "@/components/events/EventBackButton";
import { EventFlyerImage } from "@/components/events/EventFlyerImage";
import { TrackedAnchor } from "@/components/events/TrackedAnchor";
import { SaveButton } from "@/components/events/SaveButton";
import { normalizeHttpUrl } from "@/lib/events/validation";
import { isDeadlineKind } from "@/lib/events/content-kind";
import type { CampusEvent } from "@/types/event";

/**
 * Body of /events/[id]. Shared by the server page, the route's loading state
 * (which renders it straight from a list card's handoff), and the @modal
 * overlay, so all of them paint identical markup. No "use client": it stays a
 * server component under page.tsx.
 *
 * `variant="page"` sits between the masthead and footer. `variant="modal"`
 * sits inside EventModal's scrolling panel: no Back link (the shell has a close
 * button), a tighter grid, and an action bar that sticks to the panel instead
 * of the viewport.
 *
 * Phones get their own single-column order: flyer, title, host, when/where,
 * description. The desktop rail (flyer + host/source list) is hidden below md.
 *
 * Layout classes the skeletons must mirror are exported below.
 */

export type EventDetailVariant = "page" | "modal";

export const EVENT_DETAIL_MAIN_CLASS =
  "relative min-h-screen bg-canvas pb-28 md:pb-0";
export const EVENT_DETAIL_CONTAINER_CLASS =
  "relative mx-auto max-w-5xl px-4 pb-16 pt-6 sm:px-6";
export const EVENT_DETAIL_FLYER_GRID_CLASS =
  "mt-6 grid grid-cols-1 gap-10 md:mt-10 md:grid-cols-[minmax(0,18rem)_minmax(0,1fr)] md:gap-12 lg:grid-cols-[minmax(0,21rem)_minmax(0,1fr)] lg:gap-14";
export const EVENT_DETAIL_ASIDE_CLASS =
  "hidden space-y-6 md:sticky md:top-24 md:block md:self-start";
export const EVENT_DETAIL_FLYER_FRAME_CLASS =
  "relative w-full overflow-hidden rounded-xl border border-ink/10 bg-surface shadow-card";
// Phone hero: capped by viewport height so the title still shows beneath it,
// and narrow enough at 375px to clear the overlay's close button.
export const EVENT_DETAIL_MOBILE_FLYER_CLASS =
  "relative mx-auto mb-6 w-[min(16.25rem,32dvh)] overflow-hidden rounded-xl border border-ink/10 bg-surface shadow-card md:hidden";
export const EVENT_DETAIL_TILE_CLASS =
  "flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border border-ink/15 bg-canvas md:h-14 md:w-14";
export const EVENT_DETAIL_MOBILE_BAR_CLASS =
  "fixed inset-x-0 bottom-0 z-30 border-t border-ink/10 bg-canvas/95 px-4 py-3 backdrop-blur md:hidden";

/** The overlay's dialog is labelled by the event title. */
export const EVENT_MODAL_TITLE_ID = "event-modal-title";
export const EVENT_MODAL_CONTAINER_CLASS =
  "relative px-5 pb-8 pt-5 sm:px-8 sm:pb-10 sm:pt-8";
export const EVENT_MODAL_FLYER_GRID_CLASS =
  "mt-6 grid grid-cols-1 gap-8 md:mt-8 md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)] md:gap-10";
export const EVENT_MODAL_ASIDE_CLASS =
  "hidden space-y-6 md:sticky md:top-8 md:block md:self-start";
// Sticky, not fixed: the panel's open animation leaves a transform on it,
// which would make a fixed bar position against the panel anyway.
export const EVENT_MODAL_MOBILE_BAR_CLASS =
  "sticky bottom-0 z-10 border-t border-ink/10 bg-canvas px-4 py-3 md:hidden";

const SOURCE_LABELS: Record<CampusEvent["source"], string> = {
  instagram: "Instagram",
  highlander_link: "Highlander Link",
  campus_website: "UCR Events",
  club_website: "Club site",
  manual: "Manual",
};

export function LocationPinIcon() {
  return (
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
  );
}

export function EventDetailView({
  event,
  variant = "page",
}: {
  event: CampusEvent;
  variant?: EventDetailVariant;
}) {
  const isModal = variant === "modal";
  const safeRsvpUrl = normalizeHttpUrl(event.rsvpUrl);
  const safeSourceUrl = normalizeHttpUrl(event.sourceUrl);
  const primaryUrl = safeRsvpUrl ?? safeSourceUrl;
  const primaryKind = safeRsvpUrl ? "rsvp" : "view_source";
  const stamp = formatDateStamp(event.startsAt);
  const sourceLabel = SOURCE_LABELS[event.source];
  const hasImage = Boolean(event.imageUrl);
  const showHostedBy = Boolean(event.host || event.hostHandle);
  const isDeadline = isDeadlineKind(event.contentKind);
  const calendarLabel = isDeadline ? "Add reminder" : "Add to calendar";
  // Past tomorrow, relativeDay repeats the weekday or date formatDay shows.
  const relative = relativeDay(event.startsAt);
  const showRelative = relative === "Today" || relative === "Tomorrow";
  // The overlay sits on a page that already has its own h1.
  const Title = isModal ? "h2" : "h1";

  // Rendered in both the phone hero and the desktop rail. Identical src and
  // sizes let the browser resolve one URL, so the flyer downloads once.
  const flyer = event.imageUrl
    ? (() => {
        const image = (
          <EventFlyerImage
            src={event.imageUrl}
            alt={`Flyer for ${event.title}`}
            fill
            sizes={
              isModal
                ? "(max-width: 768px) 80vw, 15rem"
                : "(max-width: 768px) 80vw, (max-width: 1024px) 18rem, 21rem"
            }
            className="object-cover"
            priority
          />
        );
        // The flyer opens the original post when one is on file.
        return safeSourceUrl ? (
          <a
            href={safeSourceUrl}
            target="_blank"
            rel="noreferrer"
            aria-label={`View original post on ${sourceLabel}`}
            className="interactive-focus relative block aspect-[4/5] w-full transition-opacity hover:opacity-90"
          >
            {image}
          </a>
        ) : (
          <div className="relative aspect-[4/5] w-full">{image}</div>
        );
      })()
    : null;

  return (
    <>
      {/* Atmospheric backdrop: the flyer's mood color bleeds in, blurred low,
          then fades into canvas. On phones it runs taller to sit behind the
          flyer hero; on desktop it accents the two-column layout. */}
      {event.imageUrl && (
        <div
          aria-hidden
          className={`pointer-events-none absolute inset-x-0 top-0 overflow-hidden ${
            isModal ? "h-[26rem] md:h-72" : "h-[40vh] sm:h-[36vh]"
          }`}
        >
          <EventFlyerImage
            src={event.imageUrl}
            alt=""
            fill
            sizes={isModal ? "(max-width: 768px) 100vw, 56rem" : "100vw"}
            className="scale-125 object-cover opacity-45 blur-3xl"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-canvas/40 via-canvas/75 to-canvas" />
        </div>
      )}

      <div
        className={
          isModal ? EVENT_MODAL_CONTAINER_CLASS : EVENT_DETAIL_CONTAINER_CLASS
        }
      >
        {!isModal && <EventBackButton />}

        <article className={isModal ? undefined : "mt-7 md:mt-10"}>
          {flyer && (
            <div className={EVENT_DETAIL_MOBILE_FLYER_CLASS}>{flyer}</div>
          )}

          {/* Header: pills + title sit full-bleed across both columns for
              editorial impact, regardless of whether the flyer rail renders.
              In the overlay, right padding clears the close button (on phones
              the flyer hero already does when there is one). */}
          <header
            className={
              isModal ? (hasImage ? "md:pr-12" : "pr-12") : undefined
            }
          >
            <div className="flex flex-wrap items-center gap-2">
              {isDeadline && (
                <span className="inline-flex items-center rounded-full bg-coral/12 px-2.5 py-0.5 text-[12px] font-medium text-deep-coral">
                  Deadline
                </span>
              )}
              <CategoryBadge category={event.category} />
              {event.isFree && !isDeadline && (
                <span className="inline-flex items-center rounded-full bg-leaf/10 px-2.5 py-0.5 text-[12px] font-medium text-deep-leaf">
                  Free
                </span>
              )}
              {event.hasFreeFood && (
                <span className="inline-flex items-center rounded-full bg-gold/15 px-2.5 py-0.5 text-[12px] font-medium text-deep-gold">
                  Free food
                </span>
              )}
              {event.rsvpRequired && (
                <span className="inline-flex items-center rounded-full border border-ink/15 px-2.5 py-0.5 text-[12px] font-medium text-muted">
                  RSVP required
                </span>
              )}
            </div>

            <Title
              id={isModal ? EVENT_MODAL_TITLE_ID : undefined}
              className={`mt-3 max-w-3xl font-display font-semibold leading-[1.05] tracking-[-0.025em] text-ink md:mt-5 ${
                isModal ? "text-[28px] sm:text-[36px]" : "text-[34px] sm:text-[44px]"
              }`}
            >
              {event.title}
            </Title>

            {/* Phones: the host reads as a byline instead of a rail entry. */}
            {showHostedBy && (
              <p className="mt-2 text-[14px] text-muted md:hidden">
                by{" "}
                <span className="font-medium text-ink">
                  {event.host || event.hostHandle}
                </span>
              </p>
            )}
          </header>

          <div
            className={
              hasImage
                ? isModal
                  ? EVENT_MODAL_FLYER_GRID_CLASS
                  : EVENT_DETAIL_FLYER_GRID_CLASS
                : "mt-6 max-w-3xl md:mt-8"
            }
          >
            {flyer && (
              <aside
                className={
                  isModal ? EVENT_MODAL_ASIDE_CLASS : EVENT_DETAIL_ASIDE_CLASS
                }
              >
                <div className={EVENT_DETAIL_FLYER_FRAME_CLASS}>{flyer}</div>

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

            <div className="min-w-0">
              <section aria-label="When and where" className="space-y-3">
                <div className="flex items-center gap-3 md:gap-4">
                  <div
                    aria-hidden
                    className={`${EVENT_DETAIL_TILE_CLASS} flex-col`}
                  >
                    <span className="text-[10px] text-muted md:text-[11px]">
                      {stamp.month}
                    </span>
                    <span className="mt-0.5 font-mono text-[18px] font-semibold leading-none tabular-nums text-ink md:text-[20px]">
                      {stamp.day}
                    </span>
                  </div>
                  <div className="min-w-0">
                    <div className="font-display text-[16px] font-semibold text-ink md:text-[17px]">
                      {formatDay(event.startsAt)}
                    </div>
                    <div className="mt-0.5 text-[14px] text-muted">
                      <span className="font-mono tabular-nums text-ink/85">
                        {formatTimeRange(event.startsAt, event.endsAt)}
                      </span>
                      {showRelative && (
                        <>
                          <span aria-hidden className="mx-2 text-ink/25">
                            ·
                          </span>
                          <span>{relative}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 md:gap-4">
                  <div aria-hidden className={EVENT_DETAIL_TILE_CLASS}>
                    <LocationPinIcon />
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
                    {safeRsvpUrl ? "Registration" : "Event details"}
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
                  <EventCalendarMenu
                    event={event}
                    calendarLabel={calendarLabel}
                    surface="desktop"
                  />

                  <SaveButton eventId={event.id} surface="detail" variant="label" />
                  <ShareButton event={event} variant="text" />
                </div>
              </section>

              {/* Phones drop the divider and heading: the description simply
                  follows when/where. */}
              <section aria-label="About" className="mt-6 md:mt-10">
                <div className="hairline hidden md:block" />
                <h2 className="mt-7 hidden font-display text-[20px] font-semibold tracking-[-0.015em] text-ink md:block">
                  About
                </h2>
                <p className="max-w-prose whitespace-pre-line text-[15px] leading-relaxed text-ink/80 md:mt-4 md:text-[16px]">
                  {event.description}
                </p>

                {event.tags.length > 0 && (
                  <div className="mt-5 flex flex-wrap gap-x-3 gap-y-1 text-[13px] text-muted md:mt-6">
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
      <div
        className={
          isModal ? EVENT_MODAL_MOBILE_BAR_CLASS : EVENT_DETAIL_MOBILE_BAR_CLASS
        }
      >
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
          <EventCalendarMenu
            event={event}
            calendarLabel={calendarLabel}
            surface="mobile"
          />
          <SaveButton eventId={event.id} surface="detail" variant="icon" />
          <ShareButton event={event} variant="icon" />
        </div>
      </div>
    </>
  );
}
