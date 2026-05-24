"use client";

import Image from "next/image";
import Link from "next/link";
import { memo, type MouseEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { type CampusEvent } from "@/types/event";
import { formatTimeParts } from "@/lib/dates";
import { eventFlyerAlt, eventListLinkLabel } from "@/lib/events/a11y";
import { track } from "@/lib/analytics";
import { saveEventFeedReturn } from "@/lib/events/feed-session";
import { CATEGORY_TIME_TINT } from "@/lib/category-colors";

type EventCardProps = {
  event: CampusEvent;
  compact?: boolean;
  loadedCount?: number;
};

/**
 * Editorial listing row. Time at the left as a typographic anchor (tinted by
 * category, so the feed reads as a color rhythm), optional flyer thumbnail,
 * then content.
 */
function EventCardComponent({
  event,
  compact = false,
  loadedCount,
}: EventCardProps) {
  const router = useRouter();
  const [imageBroken, setImageBroken] = useState(false);
  const showImage = !compact && !!event.imageUrl && !imageBroken;
  const href = `/events/${event.id}`;
  const surface = compact ? "calendar_card" : "list_card";
  const { time, period } = formatTimeParts(event.startsAt);

  const onOpen = (clickEvent: MouseEvent<HTMLAnchorElement>) => {
    saveEventFeedReturn(href, {
      eventId: event.id,
      eventTop: clickEvent.currentTarget.getBoundingClientRect().top,
      loadedCount,
    });
    track("event_open", { id: event.id, category: event.category, surface });
  };

  const prefetch = () => router.prefetch(href);

  return (
    <Link
      href={href}
      onClick={onOpen}
      onMouseEnter={prefetch}
      onFocus={prefetch}
      aria-label={eventListLinkLabel(event)}
      data-event-id={event.id}
      className={`interactive-focus card-hover group relative flex w-full min-w-0 overflow-hidden rounded-xl border border-ink/15 bg-canvas ${
        compact ? "" : "min-h-[6rem]"
      }`}
    >
      {/* Time column: typographic anchor at the left edge, tinted by category. */}
      <div
        className={`flex shrink-0 flex-col items-center justify-center border-r border-ink/10 px-2 ${CATEGORY_TIME_TINT[event.category]} ${
          compact ? "w-[52px]" : "w-16 sm:w-[68px]"
        }`}
      >
        <span
          className={`font-mono font-medium leading-none text-ink tabular-nums ${
            compact ? "text-base" : "text-[22px]"
          }`}
        >
          {time}
        </span>
        {period && (
          <span
            className={`mt-1 font-mono font-medium text-muted ${
              compact ? "text-[10px]" : "text-[12px]"
            }`}
          >
            {period}
          </span>
        )}
      </div>

      {/* Portrait flyer thumbnail, when the event has a usable image. */}
      {showImage && (
        <div className="relative w-[88px] shrink-0 overflow-hidden border-r border-ink/10 bg-surface">
          <Image
            src={event.imageUrl!}
            alt={eventFlyerAlt(event)}
            fill
            sizes="88px"
            className="object-cover transition-transform duration-300 group-hover:scale-[1.03]"
            onError={() => setImageBroken(true)}
          />
        </div>
      )}

      {/* Text block. */}
      <div
        className={`flex min-w-0 flex-1 flex-col justify-center gap-1 px-4 sm:px-5 ${
          compact ? "py-2.5" : "py-3 sm:py-3.5"
        }`}
      >
        <h3 className="font-display text-[17px] font-semibold leading-[1.25] tracking-[-0.015em] text-ink line-clamp-2 break-words group-hover:underline group-hover:decoration-ink/40 group-hover:underline-offset-4">
          {event.title}
        </h3>

        <div className="flex min-w-0 items-center gap-x-1.5 text-[13px] text-muted">
          {event.isFree && !compact && (
            <>
              <span className="shrink-0 font-medium text-deep-leaf">Free</span>
              <span aria-hidden className="shrink-0 text-ink/20">·</span>
            </>
          )}
          <span className="min-w-0 flex-1 truncate">{event.host}</span>
          <span aria-hidden className="shrink-0 text-ink/20">·</span>
          <span className="min-w-0 flex-1 truncate">{event.location}</span>
        </div>
      </div>
    </Link>
  );
}

export const EventCard = memo(EventCardComponent);
EventCard.displayName = "EventCard";
