"use client";

import Image from "next/image";
import Link from "next/link";
import { memo, type MouseEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { CampusEvent } from "@/types/event";
import { formatTime } from "@/lib/dates";
import { eventFlyerAlt, eventListLinkLabel } from "@/lib/event-a11y";
import { track } from "@/lib/analytics";
import { saveEventFeedReturn } from "@/lib/event-feed-session";
import { CATEGORY_RAIL } from "@/lib/category-colors";
import { CategoryBadge } from "../ui/CategoryBadge";

type EventCardProps = {
  event: CampusEvent;
  compact?: boolean;
  loadedCount?: number;
};

/**
 * A single event rendered as a horizontal row: a hue-coded category rail, an
 * optional portrait flyer thumbnail, and a compact text block. Built to be
 * scanned a dozen at a time, not admired one at a time.
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
        compact ? "" : "min-h-[7.5rem]"
      }`}
    >
      {/* Category rail: lets a student parse a stack of cards by hue alone. */}
      <span
        aria-hidden
        className={`w-1 shrink-0 ${CATEGORY_RAIL[event.category]}`}
      />

      {/* Portrait flyer thumbnail, when the event has a usable image. */}
      {showImage && (
        <div className="relative w-24 shrink-0 overflow-hidden bg-surface">
          <Image
            src={event.imageUrl!}
            alt={eventFlyerAlt(event)}
            fill
            sizes="96px"
            className="object-cover transition-transform duration-300 group-hover:scale-[1.03]"
            onError={() => setImageBroken(true)}
          />
        </div>
      )}

      {/* Text block. */}
      <div className="flex min-w-0 flex-1 flex-col justify-center gap-1.5 px-4 py-3 sm:px-5">
        <div className="flex min-w-0 items-center gap-1.5 text-[13px] text-muted">
          <span className="shrink-0 font-mono text-[11px] tracking-[0.04em] leading-none bg-surface border border-ink/5 px-1 py-0.5 rounded-sm">
            {formatTime(event.startsAt)}
          </span>
          <span aria-hidden className="shrink-0 text-ink/20">
            ·
          </span>
          <span className="min-w-0 truncate">{event.location}</span>
        </div>

        <h3 className="font-display text-lg font-semibold leading-[1.2] tracking-[-0.015em] text-ink line-clamp-2 break-words">
          {event.title}
        </h3>

        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <span className="min-w-0 max-w-full truncate text-[13px] text-muted">
            {event.host}
          </span>
          <CategoryBadge category={event.category} />
          {event.isFree && (
            <span className="inline-flex items-center rounded-full bg-leaf/10 px-2 py-0.5 text-[11px] font-medium text-[#1f6f4e]">
              Free
            </span>
          )}
        </div>
      </div>

      {/* Chevron affordance. */}
      <div
        aria-hidden
        className="flex shrink-0 items-center pr-3 text-muted transition-colors group-hover:text-ink sm:pr-4"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-4 w-4"
        >
          <path d="m9 18 6-6-6-6" />
        </svg>
      </div>
    </Link>
  );
}

export const EventCard = memo(EventCardComponent);
EventCard.displayName = "EventCard";
