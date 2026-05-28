"use client";

import Image from "next/image";
import Link from "next/link";
import { memo, type MouseEvent, useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { type CampusEvent } from "@/types/event";
import { eventFlyerAlt, eventListLinkLabel } from "@/lib/events/a11y";
import { track } from "@/lib/analytics";
import { saveEventFeedReturn } from "@/lib/events/feed-session";
import { EventListRowTimeColumn } from "@/components/events/EventListRowTimeColumn";

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
  const descRef = useRef<HTMLParagraphElement>(null);
  const [isDescTruncated, setIsDescTruncated] = useState(false);
  const showDescription = !compact && !!event.description?.trim();

  useLayoutEffect(() => {
    if (!showDescription) return;
    const el = descRef.current;
    if (!el) return;
    const measure = () =>
      setIsDescTruncated(el.scrollHeight - el.clientHeight > 1);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [showDescription, event.description]);
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
      className={`interactive-focus group relative isolate flex w-full min-w-0 overflow-hidden rounded-xl border border-ink/10 bg-canvas transition-[border-color,box-shadow] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:border-ink/30 hover:shadow-card ${
        compact ? "" : "min-h-[6rem]"
      }`}
    >
      {/* Time column: typographic anchor at the left edge. The right edge is
         a 2px category-colored rail — magazine column-spine, full-height,
         clipped by the card's rounded corners. Carries the category signal
         without washing the column in tint. */}
      <EventListRowTimeColumn
        startsAt={event.startsAt}
        category={event.category}
        compact={compact}
      />

      {/* Portrait flyer thumbnail framed into the row: a small inset frame
         with a hairline ring + top-edge highlight gives it haptic depth at
         this size without the over-stated double-bezel a hero card would use. */}
      {showImage && (
        <div className="relative shrink-0 self-stretch py-2 pl-2">
          <div className="relative h-full w-[80px] overflow-hidden rounded-md bg-surface">
            <Image
              src={event.imageUrl!}
              alt={eventFlyerAlt(event)}
              fill
              sizes="80px"
              className="object-cover"
              onError={() => setImageBroken(true)}
            />
            <span
              aria-hidden
              className="pointer-events-none absolute inset-0 rounded-md ring-1 ring-inset ring-ink/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.45)]"
            />
          </div>
        </div>
      )}

      {/* Text block. Right-padding is widened in list mode to reserve room for
         the magnetic chevron without clipping the meta line. */}
      <div
        className={`flex min-w-0 flex-1 flex-col justify-center gap-1 pl-4 sm:pl-5 ${
          compact ? "pr-4 py-2.5" : "pr-10 py-3 sm:py-3.5"
        }`}
      >
        <h3 className="font-display text-[17px] font-semibold leading-[1.25] tracking-[-0.015em] text-ink line-clamp-2 break-words group-hover:underline group-hover:decoration-ink/30 group-hover:underline-offset-[5px] group-hover:decoration-[1.5px]">
          {event.title}
        </h3>

        <div className="flex min-w-0 items-center gap-x-1.5 text-[13px] text-muted">
          {event.isFree && !compact && (
            <>
              <span className="shrink-0 text-[11px] font-semibold uppercase tracking-[0.08em] text-deep-leaf">
                Free
              </span>
              <span aria-hidden className="shrink-0 text-ink/20">·</span>
            </>
          )}
          {event.host ? (
            <span className="min-w-0 truncate">{event.host}</span>
          ) : null}
        </div>

        <div className="flex min-w-0 items-center gap-x-1 text-[13px] text-muted">
          <svg
            aria-hidden
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-3.5 w-3.5 shrink-0 text-ink/40"
          >
            <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
            <circle cx="12" cy="10" r="3" />
          </svg>
          <span className="min-w-0 truncate">{event.location}</span>
        </div>

        {showDescription && (
          <div className="relative mt-0.5">
            <p
              ref={descRef}
              className="line-clamp-2 text-[13px] leading-snug text-ink/70"
            >
              {event.description}
            </p>
            {isDescTruncated && (
              <span
                aria-hidden
                className="pointer-events-none absolute bottom-0 right-0 bg-canvas pl-6 text-[13px] leading-snug text-ink/70"
                style={{
                  maskImage:
                    "linear-gradient(to right, transparent 0, black 18px)",
                  WebkitMaskImage:
                    "linear-gradient(to right, transparent 0, black 18px)",
                }}
              >
                … <span className="text-ink underline decoration-ink/30 underline-offset-[3px]">see more</span>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Magnetic hover affordance: a feather-light chevron that fades in from
         the right with a small diagonal translate. Reads as "openable" without
         the heaviness of a button. List surface only. */}
      {!compact && (
        <span
          aria-hidden
          className="pointer-events-none absolute right-3.5 top-1/2 -translate-x-1 -translate-y-1/2 text-ink/40 opacity-0 transition-[opacity,transform,color] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:translate-x-0 group-hover:text-ink group-hover:opacity-100"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-3.5 w-3.5"
          >
            <path d="M7 17 17 7" />
            <path d="M9 7h8v8" />
          </svg>
        </span>
      )}
    </Link>
  );
}

export const EventCard = memo(EventCardComponent);
EventCard.displayName = "EventCard";
