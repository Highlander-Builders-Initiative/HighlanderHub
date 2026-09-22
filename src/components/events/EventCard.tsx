"use client";

import Link from "next/link";
import { memo, type MouseEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { type CampusEvent, EVENT_CATEGORY_LABELS } from "@/types/event";
import { FlyerPoster } from "@/components/events/FlyerPoster";
import { ClubAvatar } from "@/components/ui/ClubAvatar";
import { eventFlyerAlt, eventListLinkLabel } from "@/lib/events/a11y";
import { isDeadlineKind } from "@/lib/events/content-kind";
import { isOnlineLocation } from "@/lib/events/location";
import { formatAllDay, formatTimeParts } from "@/lib/dates";
import { CATEGORY_PILL, DEADLINE_PILL } from "@/lib/category-colors";
import { track } from "@/lib/analytics";
import { saveEventFeedReturn } from "@/lib/events/feed-session";
import { stashEventForDetail } from "@/lib/events/detail-handoff";

type EventCardProps = {
  event: CampusEvent;
  loadedCount?: number;
};

const MAX_HOST_AVATARS = 3;
const PILL = "rounded-full px-2.5 py-0.5 text-[13px] font-medium sm:px-3 sm:text-[14px]";

/** "A", "A & B", "A, B & C" */
function joinHostNames(names: string[]): string {
  if (names.length < 2) return names[0] ?? "";
  return `${names.slice(0, -1).join(", ")} & ${names[names.length - 1]}`;
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
  const { time, period } = formatTimeParts(event.startsAt);
  // A deadline's time is its cutoff, even at midnight.
  const allDay = isDeadline ? null : formatAllDay(event.startsAt, event.endsAt);
  const timeLabel = allDay ?? `${time} ${period}`;
  const hosts = (event.hosts?.length ? event.hosts : [event]).filter(
    (host) => host.host || host.hostHandle
  );
  const location = event.location?.trim();
  // A free-food category and the free-food flag are the same fact; one pill.
  const hasFreeFood = event.hasFreeFood || event.category === "free_food";
  const categoryPill = event.category === "free_food" ? null : CATEGORY_PILL[event.category];

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
          {timeLabel}
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
            <span className="min-w-0 truncate">
              By {joinHostNames(hosts.map((host) => host.host || host.hostHandle!))}
            </span>
          </div>
        )}

        {location ? (
          <div className="mt-1.5 flex min-w-0 items-center gap-2 text-[14px] text-faint sm:text-[16px]">
            {/* Same 22px column as the avatars, so the two rows' text lines up. */}
            <span className="flex w-[22px] shrink-0 justify-center">
              <svg
                aria-hidden
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-[18px] w-[18px]"
              >
                {isOnlineLocation(location) ? (
                  <>
                    <rect x="2.5" y="6" width="13.5" height="12" rx="2.5" />
                    <path d="m16 10.5 4.4-2.9a.6.6 0 0 1 .9.5v7.8a.6.6 0 0 1-.9.5L16 13.5" />
                  </>
                ) : (
                  <>
                    <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
                    <circle cx="12" cy="10" r="3" />
                  </>
                )}
              </svg>
            </span>
            <span className="min-w-0 truncate">{location}</span>
          </div>
        ) : null}

        <div className="mt-4 flex flex-wrap gap-1.5">
          {isDeadline && (
            <span className={`${PILL} ${DEADLINE_PILL.highlight} ${DEADLINE_PILL.text}`}>Deadline</span>
          )}
          {categoryPill && (
            <span className={`${PILL} ${categoryPill.highlight} ${categoryPill.text}`}>
              {EVENT_CATEGORY_LABELS[event.category].split(" / ")[0]}
            </span>
          )}
          {hasFreeFood && (
            <span className={`${PILL} ${CATEGORY_PILL.free_food.highlight} ${CATEGORY_PILL.free_food.text}`}>
              Free food
            </span>
          )}
          {/* Unfilled: a note about attending, not a kind of event. */}
          {event.rsvpRequired && (
            <span className={`${PILL} text-ink/70 ring-1 ring-inset ring-ink/15`}>RSVP</span>
          )}
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
