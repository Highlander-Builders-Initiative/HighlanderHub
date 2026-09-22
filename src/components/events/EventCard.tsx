"use client";

import Link from "next/link";
import { memo, type MouseEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { CampusEvent } from "@/types/event";
import { FlyerPoster } from "@/components/events/FlyerPoster";
import { ClubAvatar } from "@/components/ui/ClubAvatar";
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

const MAX_HOST_AVATARS = 3;
const PILL = "rounded-full px-2.5 py-0.5 text-[13px] font-medium sm:px-3 sm:text-[14px]";

/**
 * Pin or camera for the where-row, drawn to sit in the text like a glyph. Each
 * viewBox hugs its ink, so the icon's left edge lines up with the avatars' and
 * the row gap is the gap you see. Heights are in em so the icon follows the
 * 14→16px text step, and strokes render at ~0.09em, Bricolage's regular stem.
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
      viewBox="2.85 0.85 18.3 22.3"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.3"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-[0.9em] w-[0.74em] shrink-0"
    >
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}

/**
 * Feed listing row: start time, title, hosts with their club pictures, where,
 * and a row of tags, with the flyer pinned at the right edge.
 */
function EventCardComponent({ event, loadedCount }: EventCardProps) {
  const router = useRouter();
  const [imageBroken, setImageBroken] = useState(false);
  const showImage = !!event.imageUrl && !imageBroken;
  const isDeadline = isDeadlineKind(event.contentKind);
  const hosts = (event.hosts?.length ? event.hosts : [event]).filter(
    (host) => host.host || host.hostHandle
  );
  const location = event.location?.trim();

  const href = `/events/${event.id}`;
  const onOpen = (clickEvent: MouseEvent<HTMLAnchorElement>) => {
    stashEventForDetail(event);
    saveEventFeedReturn(href, {
      eventId: event.id,
      eventTop: clickEvent.currentTarget.getBoundingClientRect().top,
      loadedCount,
    });
    track("event_open", { id: event.id, category: event.category, surface: "list_card" });
  };

  const prefetch = () => router.prefetch(href);

  // Cards skip layout, paint and hit-testing while off screen, so a feed with
  // hundreds of loaded events stays about as cheap as one page. Unrendered
  // cards hold the measured median height (207px mobile, 202px sm+); `auto`
  // keeps each card's real height once it has rendered.
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
      className="interactive-focus card-hover group flex w-full min-w-0 gap-4 rounded-2xl border border-ink/10 bg-canvas p-4 shadow-card transition-[border-color,box-shadow] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] [contain-intrinsic-height:auto_207px] [content-visibility:auto] hover:border-ink/30 hover:shadow-cardHover sm:gap-5 sm:p-5 sm:[contain-intrinsic-height:auto_202px]"
    >
      <div className="flex min-w-0 flex-1 flex-col">
        <p className="text-[14px] leading-5 tabular-nums text-faint sm:text-[15px]">
          {isDeadline && <span className={`font-medium ${DEADLINE_PILL.text}`}>Due </span>}
          {eventTimeLabel(event, "start")}
        </p>

        <h3 className="mt-2 font-display text-[18px] font-semibold leading-[1.25] tracking-[-0.015em] text-ink line-clamp-2 break-words group-hover:underline group-hover:decoration-ink/30 group-hover:underline-offset-[5px] group-hover:decoration-[1.5px] sm:text-[20px]">
          {event.title}
        </h3>

        {hosts.length > 0 && (
          <div className="mt-2.5 flex min-w-0 items-center gap-2 text-[14px] text-faint sm:text-[16px]">
            <span className="flex shrink-0 -space-x-1.5">
              {hosts.slice(0, MAX_HOST_AVATARS).map((host) => (
                <span
                  key={host.hostHandle || host.host}
                  className="rounded-full ring-2 ring-canvas"
                >
                  <ClubAvatar
                    handle={host.hostHandle}
                    name={host.host || host.hostHandle || ""}
                    size={22}
                  />
                </span>
              ))}
            </span>
            {/* Phones name hosts by handle; full club names truncate there. */}
            <span className="min-w-0 truncate">
              By <span className="sm:hidden">{hostHandlesByline(hosts)}</span>
              <span className="hidden sm:inline">{hostNamesByline(hosts)}</span>
            </span>
          </div>
        )}

        {location ? (
          <div className="mt-1.5 flex min-w-0 items-center gap-[0.4em] text-[14px] text-faint sm:text-[16px]">
            <LocationIcon online={isOnlineLocation(location)} />
            <span className="min-w-0 truncate">{location}</span>
          </div>
        ) : null}

        <div className="mt-4 flex flex-wrap gap-1.5">
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
         and every card keeps the same rhythm. */}
      {showImage && (
        <div className="flex h-[var(--flyer-max-h)] w-[var(--flyer-max-w)] shrink-0 items-start justify-end [--flyer-max-h:100px] [--flyer-max-w:80px] sm:[--flyer-max-h:150px] sm:[--flyer-max-w:120px]">
          <FlyerPoster
            src={event.imageUrl!}
            alt={eventFlyerAlt(event)}
            sizes="(min-width: 640px) 120px, 80px"
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
