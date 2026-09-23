"use client";

import Link from "next/link";
import { memo, type MouseEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { CampusEvent } from "@/types/event";
import { FlyerPoster } from "@/components/events/FlyerPoster";
import { HostAvatars, eventHosts } from "@/components/events/HostAvatars";
import { eventFlyerAlt, eventListLinkLabel } from "@/lib/events/a11y";
import { isDeadlineKind } from "@/lib/events/content-kind";
import { isOnlineLocation } from "@/lib/events/location";
import { hostHandlesByline, hostNamesByline } from "@/lib/events/host-byline";
import { eventTimeLabel } from "@/lib/dates";
import { DEADLINE_PILL, eventTags } from "@/lib/category-colors";
import { track } from "@/lib/analytics";
import { saveEventFeedReturn } from "@/lib/events/feed-session";
import { stashEventForDetail } from "@/lib/events/detail-handoff";

type EventCardProps = {
  event: CampusEvent;
  loadedCount?: number;
};

/**
 * Width of the icon column that leads the hosts and where rows: one avatar
 * fills it and the where-row icon is centered in it, so both rows' text
 * starts at the same x. 16px is Luma's proportion, an avatar about the
 * body text's size.
 */
const LEAD_COLUMN_PX = 16;
/** From lg the pills step down to 12px, Luma's badge size, so the tag row
 *  stays a footnote under the title. */
const PILL =
  "rounded-full px-2.5 py-0.5 text-[13px] font-medium sm:px-3 sm:text-[14px] lg:px-2 lg:text-[12px]";
/** Compact rows use the 12px pill at every width. */
const ROW_PILL = "rounded-full px-2 py-0.5 text-[12px] font-medium";

/**
 * Pin or camera for the where-row, drawn to sit in the text like a glyph. Each
 * viewBox hugs its ink, so the icon nearly fills the lead column (a 1em pin is
 * as tall as the avatar at 16px) and the space before the text stays close to
 * the avatar's. Sizes are in em so the icon follows the 14→16px text step, and
 * strokes render at ~0.09em, the body face's regular stem.
 */
function LocationIcon({ online }: { online: boolean }) {
  return online ? (
    <svg
      aria-hidden
      viewBox="1.55 5.05 20.7 13.9"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-[0.68em] w-[1.01em] shrink-0"
    >
      <rect x="2.5" y="6" width="13.5" height="12" rx="2.5" />
      <path d="m16 10.5 4.4-2.9a.6.6 0 0 1 .9.5v7.8a.6.6 0 0 1-.9.5L16 13.5" />
    </svg>
  ) : (
    <svg
      aria-hidden
      viewBox="3 1 18 22"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-[1em] w-[0.818em] shrink-0"
    >
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}

/**
 * What both feed shapes do on open: hand the event to the detail view,
 * remember where the reader was in the feed, and prefetch on intent.
 */
function useEventLink(
  event: CampusEvent,
  loadedCount: number | undefined,
  surface: "list_card" | "list_row"
) {
  const router = useRouter();
  const href = `/events/${event.id}`;
  const prefetch = () => router.prefetch(href);
  const onOpen = (clickEvent: MouseEvent<HTMLAnchorElement>) => {
    stashEventForDetail(event);
    saveEventFeedReturn(href, {
      eventId: event.id,
      eventTop: clickEvent.currentTarget.getBoundingClientRect().top,
      loadedCount,
    });
    track("event_open", { id: event.id, category: event.category, surface });
  };
  return { href, onOpen, prefetch };
}

/**
 * Feed listing row: start time, title, hosts with their club pictures, where,
 * and a row of tags, with the flyer pinned at the right edge.
 */
function EventCardComponent({ event, loadedCount }: EventCardProps) {
  const { href, onOpen, prefetch } = useEventLink(event, loadedCount, "list_card");
  const [imageBroken, setImageBroken] = useState(false);
  const showImage = !!event.imageUrl && !imageBroken;
  const isDeadline = isDeadlineKind(event.contentKind);
  const hosts = eventHosts(event);
  const location = event.location?.trim();

  // Cards skip layout, paint and hit-testing while off screen, so a feed with
  // hundreds of loaded events stays about as cheap as one page. Unrendered
  // cards hold the measured median height (207px mobile, 202px sm+, 178px
  // lg+); `auto` keeps each card's real height once it has rendered.
  // From lg the card is flat: a faint edge, no shadow, Luma's tighter inset
  // (DESIGN.md, Event Card). Phones keep the resting lift.
  return (
    <Link
      href={href}
      // Opens as an overlay (@modal intercepted route); the list keeps its place.
      scroll={false}
      onClick={onOpen}
      onMouseEnter={prefetch}
      onFocus={prefetch}
      aria-label={eventListLinkLabel(event)}
      data-event-id={event.id}
      className="interactive-focus card-hover group flex w-full min-w-0 gap-4 rounded-2xl border border-ink/10 bg-canvas p-4 shadow-card transition-[border-color,box-shadow] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] [contain-intrinsic-height:auto_207px] [content-visibility:auto] hover:border-ink/30 hover:shadow-cardHover sm:gap-5 sm:p-5 sm:[contain-intrinsic-height:auto_202px] lg:rounded-[20px] lg:border-ink/[0.06] lg:py-3.5 lg:pl-[18px] lg:pr-3.5 lg:shadow-none lg:[contain-intrinsic-height:auto_178px] lg:hover:shadow-none"
    >
      <div className="flex min-w-0 flex-1 flex-col">
        <p className="text-[14px] leading-5 tabular-nums text-faint sm:text-[15px]">
          {isDeadline && <span className={`font-medium ${DEADLINE_PILL.text}`}>Due </span>}
          {eventTimeLabel(event, "start")}
        </p>

        <h3 className="mt-2 text-[18px] font-semibold leading-[1.25] tracking-[-0.01em] text-ink line-clamp-2 break-words sm:text-[20px] lg:mt-1 lg:font-medium">
          {event.title}
        </h3>

        {hosts.length > 0 && (
          <div className="mt-2.5 flex min-w-0 items-center gap-2 text-[14px] text-faint sm:text-[16px]">
            <HostAvatars hosts={hosts} size={LEAD_COLUMN_PX} />
            {/* Phones name hosts by handle; full club names truncate there. */}
            <span className="min-w-0 truncate">
              By <span className="sm:hidden">{hostHandlesByline(hosts)}</span>
              <span className="hidden sm:inline">{hostNamesByline(hosts)}</span>
            </span>
          </div>
        )}

        {location ? (
          <div className="mt-1.5 flex min-w-0 items-center gap-2 text-[14px] text-faint sm:text-[16px]">
            <span className="flex shrink-0 justify-center" style={{ width: LEAD_COLUMN_PX }}>
              <LocationIcon online={isOnlineLocation(location)} />
            </span>
            <span className="min-w-0 truncate">{location}</span>
          </div>
        ) : null}

        <div className="mt-4 flex flex-wrap gap-1.5 lg:mt-3">
          {eventTags(event).map((tag) => (
            <span key={tag.label} className={`${PILL} ${tag.highlight} ${tag.text}`}>
              {tag.label}
            </span>
          ))}
        </div>
      </div>

      {/* Flyer pinned whole in a fixed 4:5 slot (Instagram's portrait post),
         anchored to the slot's top-right corner. Squares, reel covers and
         landscape posts keep their own shape inside it, so nothing is cropped
         and every card keeps the same rhythm.
         The slot takes the width left once the text column has 181px (its
         width on a 375px phone, where the bigger slot clamps no more titles
         than the old 80x100 did): 263px = that column plus the gutters,
         padding and gap. So it grows from 80x100 on the narrowest phones to
         the sm+ size, 120x150, from a 383px screen up. */}
      {showImage && (
        <div className="flex h-[var(--flyer-max-h)] w-[var(--flyer-max-w)] shrink-0 items-start justify-end [--flyer-max-h:calc(var(--flyer-max-w)*1.25)] [--flyer-max-w:clamp(80px,100vw_-_263px,120px)]">
          <FlyerPoster
            src={event.imageUrl!}
            alt={eventFlyerAlt(event)}
            sizes="120px"
            className="rounded-lg bg-ink/[0.05] ring-1 ring-ink/10"
            onError={() => setImageBroken(true)}
          />
        </div>
      )}
    </Link>
  );
}

export const EventCard = memo(EventCardComponent);
EventCard.displayName = "EventCard";

/**
 * The feed's compact view: one line of a day's list, about 70px tall on
 * desktop and 84px on phones, where a card is 200. Rows are divided by
 * hairlines inside one surface per day (EventsFeedColumn).
 *
 * From lg, four columns: a 40x50 flyer thumbnail, the start time, the title
 * over its hosts, and the where over the tags, right-aligned. Phones stack
 * three lines beside the thumbnail: time and where, the title, then the hosts
 * with the tags at the end. The two groups are `display: contents` there, so
 * their children take the phone grid's areas directly.
 */
function EventCompactRowComponent({ event, loadedCount }: EventCardProps) {
  const { href, onOpen, prefetch } = useEventLink(event, loadedCount, "list_row");
  const [imageBroken, setImageBroken] = useState(false);
  const showImage = !!event.imageUrl && !imageBroken;
  const isDeadline = isDeadlineKind(event.contentKind);
  const hosts = eventHosts(event);
  const location = event.location?.trim();
  // The Topics filter already sorts by category, so a row keeps only the tags
  // that change what you do: Deadline, Free food, RSVP.
  const tags = eventTags(event).filter((tag) => tag.kind !== "category");

  // The focus ring is drawn inside the row: an outside ring would run under
  // the rows around it. First and last rows round with the day's surface so
  // the hover wash and the ring follow its corners.
  return (
    <Link
      href={href}
      // Opens as an overlay (@modal intercepted route); the list keeps its place.
      scroll={false}
      onClick={onOpen}
      onMouseEnter={prefetch}
      onFocus={prefetch}
      aria-label={eventListLinkLabel(event)}
      data-event-id={event.id}
      className="interactive-focus grid w-full min-w-0 grid-cols-[40px_auto_minmax(0,1fr)_auto] items-center gap-x-2.5 gap-y-0.5 py-2.5 pl-2.5 pr-3.5 transition-colors duration-150 [contain-intrinsic-height:auto_84px] [content-visibility:auto] [grid-template-areas:'thumb_time_loc_loc'_'thumb_title_title_title'_'thumb_host_host_tags'] first:rounded-t-[19px] last:rounded-b-[19px] hover:bg-ink/[0.03] focus-visible:!shadow-none focus-visible:!outline-offset-[-3px] lg:grid-cols-[40px_72px_minmax(0,1fr)_auto] lg:gap-x-3.5 lg:gap-y-0 lg:pr-4 lg:[contain-intrinsic-height:auto_70px] lg:[grid-template-areas:'thumb_time_main_aside']"
    >
      <span className="flex h-[50px] w-10 items-center justify-center [--flyer-max-h:50px] [--flyer-max-w:40px] [grid-area:thumb]">
        {showImage ? (
          <FlyerPoster
            src={event.imageUrl!}
            alt={eventFlyerAlt(event)}
            sizes="40px"
            className="rounded-md bg-ink/[0.05] ring-1 ring-ink/10"
            onError={() => setImageBroken(true)}
          />
        ) : (
          <span aria-hidden className="h-[50px] w-10 rounded-md bg-ink/[0.05]" />
        )}
      </span>

      {/* Deadlines read "Due 11:59 PM" inline on phones, stacked from lg. */}
      <p className="whitespace-nowrap text-[13px] leading-[18px] tabular-nums text-faint [grid-area:time] lg:whitespace-normal lg:text-[14px] lg:leading-5">
        {isDeadline && <span className={`font-medium ${DEADLINE_PILL.text} lg:block`}>Due </span>}
        {eventTimeLabel(event, "start")}
      </p>

      <div className="contents lg:block lg:min-w-0 lg:[grid-area:main]">
        <h3 className="truncate text-[15px] font-medium leading-5 tracking-[-0.005em] text-ink [grid-area:title] lg:text-[16px] lg:leading-[1.35]">
          {event.title}
        </h3>
        {hosts.length > 0 && (
          <div className="flex min-w-0 items-center gap-2 text-[13px] leading-[18px] text-faint [grid-area:host] lg:mt-0.5 lg:text-[14px] lg:leading-5">
            <HostAvatars hosts={hosts} size={LEAD_COLUMN_PX} />
            {/* Phones name hosts by handle, as the cards do. */}
            <span className="min-w-0 truncate">
              By <span className="sm:hidden">{hostHandlesByline(hosts)}</span>
              <span className="hidden sm:inline">{hostNamesByline(hosts)}</span>
            </span>
          </div>
        )}
      </div>

      {(location || tags.length > 0) && (
        <div className="contents lg:flex lg:min-w-0 lg:max-w-[200px] lg:flex-col lg:items-end lg:gap-1 lg:[grid-area:aside]">
          {location && (
            <div className="flex min-w-0 items-center gap-1.5 text-[13px] leading-[18px] text-faint [grid-area:loc] lg:max-w-full lg:text-[14px] lg:leading-5">
              <LocationIcon online={isOnlineLocation(location)} />
              <span className="min-w-0 truncate">{location}</span>
            </div>
          )}
          {tags.length > 0 && (
            <div className="flex gap-1 justify-self-end [grid-area:tags] lg:gap-1.5">
              {tags.map((tag) => (
                <span key={tag.label} className={`${ROW_PILL} ${tag.highlight} ${tag.text}`}>
                  {tag.label}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </Link>
  );
}

export const EventCompactRow = memo(EventCompactRowComponent);
EventCompactRow.displayName = "EventCompactRow";
