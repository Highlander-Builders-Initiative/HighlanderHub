import { eventTags } from "@/lib/category-colors";
import { eventTimeLabel, formatDay, relativeDay } from "@/lib/dates";
import { EventCalendarMenu } from "@/components/events/EventCalendarMenu";
import { ShareButton } from "@/components/events/ShareButton";
import { EventBackButton } from "@/components/events/EventBackButton";
import { FlyerPoster } from "@/components/events/FlyerPoster";
import { HostAvatars, eventHosts } from "@/components/events/HostAvatars";
import { TrackedAnchor } from "@/components/events/TrackedAnchor";
import { normalizeHttpUrl } from "@/lib/events/validation";
import { isDeadlineKind } from "@/lib/events/content-kind";
import { hostNamesByline } from "@/lib/events/host-byline";
import { isOnlineLocation } from "@/lib/events/location";
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
 * It reads in the feed's language (DESIGN.md, Event Detail): flat canvas, no
 * boxes inside the panel, the card's "By" line with club pictures, and when /
 * where as icon rows. Phones get their own single-column order: flyer, title,
 * host, when/where, description. The desktop rail (the flyer) is hidden below
 * md.
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
// Rails bound the flyer (see .flyer-fit) to their width, with tall reel
// covers capped above the fold, and pin it to their left edge.
export const EVENT_DETAIL_ASIDE_CLASS =
  "hidden space-y-6 md:sticky md:top-24 md:block md:self-start [--flyer-anchor:left_top] [--flyer-max-h:min(32rem,70dvh)] [--flyer-max-w:18rem] lg:[--flyer-max-w:21rem]";
// The flyer is shown whole at its own shape, so the frame (edge, hairline) is
// drawn on the image itself rather than on a fixed crop box; flat, as on the
// feed. Its fill is the placeholder until the image paints over it.
export const EVENT_DETAIL_FLYER_CLASS =
  "block rounded-xl bg-ink/[0.04] ring-1 ring-ink/10";
// Phone hero: capped by viewport height so the title still shows beneath it,
// and narrow enough at 375px to clear the overlay's close button.
export const EVENT_DETAIL_MOBILE_FLYER_CLASS =
  "mb-6 flex justify-center md:hidden [--flyer-max-h:min(20.3125rem,40dvh)] [--flyer-max-w:min(16.25rem,100vw_-_2.5rem)]";
// When and where rows: the icon sits in a lead column one text line tall, as
// the pin does on a feed card, so both rows' text starts at the same x.
const INFO_ICON_CLASS = "flex h-6 w-5 shrink-0 items-center justify-center text-muted";
export const EVENT_DETAIL_MOBILE_BAR_CLASS =
  "fixed inset-x-0 bottom-0 z-30 border-t border-ink/10 bg-canvas/95 px-4 py-3 backdrop-blur md:hidden";

/** The overlay's dialog is labelled by the event title. */
export const EVENT_MODAL_TITLE_ID = "event-modal-title";
export const EVENT_MODAL_CONTAINER_CLASS =
  "relative px-5 pb-8 pt-5 sm:px-8 sm:pb-10 sm:pt-8";
export const EVENT_MODAL_FLYER_GRID_CLASS =
  "mt-6 grid grid-cols-1 gap-8 md:mt-8 md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)] md:gap-10";
export const EVENT_MODAL_ASIDE_CLASS =
  "hidden space-y-6 md:sticky md:top-8 md:block md:self-start [--flyer-anchor:left_top] [--flyer-max-h:min(32rem,70dvh)] [--flyer-max-w:15rem]";
// Sticky, not fixed: the panel's open animation leaves a transform on it,
// which would make a fixed bar position against the panel anyway.
export const EVENT_MODAL_MOBILE_BAR_CLASS =
  "sticky bottom-0 z-10 border-t border-ink/10 bg-canvas px-4 py-3 md:hidden";

const SOURCE_LABELS: Record<CampusEvent["source"], string> = {
  instagram: "Instagram",
  campus_website: "UCR Events",
  club_website: "Club site",
  manual: "Manual",
};

function CalendarIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-[18px] w-[18px]"
    >
      <rect x="3.5" y="5" width="17" height="15.5" rx="2.5" />
      <path d="M16 3v4M8 3v4M3.5 10h17" />
    </svg>
  );
}

function LocationPinIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-[18px] w-[18px]"
    >
      <path d="M12 21s-7-7.5-7-12a7 7 0 1 1 14 0c0 4.5-7 12-7 12Z" />
      <circle cx="12" cy="9" r="2.5" />
    </svg>
  );
}

function VideoCallIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-[18px] w-[18px]"
    >
      <rect x="2.5" y="6" width="13.5" height="12" rx="2.5" />
      <path d="m16 10.5 4.4-2.9a.6.6 0 0 1 .9.5v7.8a.6.6 0 0 1-.9.5L16 13.5" />
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
  const sourceLabel = SOURCE_LABELS[event.source];
  const hasImage = Boolean(event.imageUrl);
  const hosts = eventHosts(event);
  const description = event.description?.trim();
  const hasAbout = Boolean(description) || event.tags.length > 0;
  const isDeadline = isDeadlineKind(event.contentKind);
  const calendarLabel = isDeadline ? "Add reminder" : "Add to calendar";
  // Past tomorrow, relativeDay repeats the weekday or date formatDay shows.
  const relative = relativeDay(event.startsAt);
  const showRelative = relative === "Today" || relative === "Tomorrow";
  // The overlay sits on a page that already has its own h1.
  const Title = isModal ? "h2" : "h1";

  // Rendered in both the phone hero and the desktop rail. Identical src and
  // sizes let the browser resolve one URL, so the flyer downloads once. The
  // hero sits above the title, so it holds its space until the shape is known.
  const renderFlyer = (placement: "hero" | "rail") => {
    if (!event.imageUrl) return null;
    const image = (
      <FlyerPoster
        src={event.imageUrl}
        alt={`Flyer for ${event.title}`}
        sizes={
          isModal
            ? "(max-width: 768px) 80vw, 15rem"
            : "(max-width: 768px) 80vw, (max-width: 1024px) 18rem, 21rem"
        }
        className={EVENT_DETAIL_FLYER_CLASS}
        reserveSpace={placement === "hero"}
        priority
      />
    );
    // The flyer opens the original post when one is on file. The link hugs
    // the flyer so its focus ring traces the same edge.
    return safeSourceUrl ? (
      <a
        href={safeSourceUrl}
        target="_blank"
        rel="noreferrer"
        aria-label={`View original post on ${sourceLabel}`}
        className="interactive-focus block w-fit max-w-full rounded-xl transition-opacity hover:opacity-90"
      >
        {image}
      </a>
    ) : (
      image
    );
  };

  return (
    <>
      {/* No flyer-colored wash behind the header: the panel is flat canvas,
          like the feed (DESIGN.md, Meaning-Carrying: no mood-color washes). */}
      <div
        className={
          isModal ? EVENT_MODAL_CONTAINER_CLASS : EVENT_DETAIL_CONTAINER_CLASS
        }
      >
        {!isModal && <EventBackButton />}

        {/* Captions and locations can carry long unbroken runs (links,
            divider lines). They wrap at the column's edge instead of widening
            the panel into a sideways scroll. break-word leaves min-content
            sizes alone, so nothing else in the layout reflows. */}
        <article className={isModal ? "break-words" : "mt-7 break-words md:mt-10"}>
          {hasImage && (
            <div className={EVENT_DETAIL_MOBILE_FLYER_CLASS}>
              {renderFlyer("hero")}
            </div>
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
              {eventTags(event).map((tag) => (
                <span
                  key={tag.label}
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-[12px] font-medium ${tag.highlight} ${tag.text}`}
                >
                  {tag.label}
                </span>
              ))}
            </div>

            <Title
              id={isModal ? EVENT_MODAL_TITLE_ID : undefined}
              className={`mt-3 max-w-3xl font-semibold leading-[1.05] tracking-[-0.02em] text-ink md:mt-5 ${
                isModal ? "text-[28px] sm:text-[36px]" : "text-[34px] sm:text-[44px]"
              }`}
            >
              {event.title}
            </Title>

            {/* The feed card's byline, with its club pictures: every host by
                name. It wraps here rather than truncating. */}
            {hosts.length > 0 && (
              <div className="mt-3 flex items-start gap-2 text-[15px] text-muted md:mt-4">
                <span className="mt-0.5">
                  <HostAvatars hosts={hosts} size={20} />
                </span>
                <p className="min-w-0">
                  By <span className="font-medium text-ink">{hostNamesByline(hosts)}</span>
                </p>
              </div>
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
            {hasImage && (
              <aside
                className={
                  isModal ? EVENT_MODAL_ASIDE_CLASS : EVENT_DETAIL_ASIDE_CLASS
                }
              >
                {renderFlyer("rail")}
              </aside>
            )}

            <div className="min-w-0">
              <section aria-label="When and where" className="space-y-3.5">
                <div className="flex gap-3">
                  <span aria-hidden className={INFO_ICON_CLASS}>
                    <CalendarIcon />
                  </span>
                  <div className="min-w-0">
                    <div className="text-[16px] font-semibold leading-6 text-ink md:text-[17px]">
                      {formatDay(event.startsAt)}
                    </div>
                    <div className="mt-0.5 text-[14px] text-muted">
                      <span className="tabular-nums text-ink/85">
                        {eventTimeLabel(event, "span")}
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

                {event.location?.trim() ? (
                  <div className="flex gap-3">
                    <span aria-hidden className={INFO_ICON_CLASS}>
                      {isOnlineLocation(event.location) ? (
                        <VideoCallIcon />
                      ) : (
                        <LocationPinIcon />
                      )}
                    </span>
                    <div className="min-w-0 text-[16px] leading-6 text-ink">
                      {event.location}
                    </div>
                  </div>
                ) : null}
              </section>

              {/* Actions, desktop only; phones use the sticky bottom bar. A
                plain row, not a box: nothing nests inside the panel. */}
              <section
                aria-label={safeRsvpUrl ? "Registration" : "Event links"}
                className="mt-8 hidden md:block"
              >
                {!primaryUrl && (
                  <p className="mb-4 text-[14px] text-ink/75">
                    No external link is on file. Check with the host for the
                    latest info.
                  </p>
                )}
                <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
                  {primaryUrl && (
                    <TrackedAnchor
                      event="primary"
                      ctaKind={primaryKind}
                      eventId={event.id}
                      surface="desktop"
                      href={primaryUrl}
                      className="interactive-focus inline-flex min-h-12 items-center gap-2 rounded-lg bg-ink px-6 py-3 text-sm font-medium text-canvas transition-opacity hover:opacity-85"
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

                  <ShareButton event={event} variant="text" />

                  {primaryUrl && (
                    <span className="ml-auto text-[13px] text-muted">
                      via {sourceLabel}
                    </span>
                  )}
                </div>
              </section>

              {/* Phones drop the divider and heading: the description simply
                  follows when/where. With no caption and no tags there is
                  nothing to title, so the section goes. */}
              {hasAbout && (
                <section aria-label="About" className="mt-6 md:mt-10">
                  <div className="hairline hidden md:block" />
                  <h2 className="mt-7 hidden text-[18px] font-semibold tracking-[-0.01em] text-ink md:block">
                    About
                  </h2>
                  {description && (
                    <p className="max-w-prose whitespace-pre-line text-[15px] leading-relaxed text-ink/80 md:mt-3 md:text-[16px]">
                      {description}
                    </p>
                  )}

                  {event.tags.length > 0 && (
                    <div className="mt-5 flex flex-wrap gap-x-3 gap-y-1 text-[13px] text-muted md:mt-6">
                      {event.tags.map((t) => (
                        <span key={t}>#{t.replace(/\s+/g, "")}</span>
                      ))}
                    </div>
                  )}
                </section>
              )}
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
              className="interactive-focus flex-1 inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-ink px-4 py-3 text-sm font-medium text-canvas"
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
          <ShareButton event={event} variant="icon" />
        </div>
      </div>
    </>
  );
}
