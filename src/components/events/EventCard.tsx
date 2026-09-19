"use client";

import Link from "next/link";
import { memo, type MouseEvent, useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { type CampusEvent } from "@/types/event";
import { FlyerPoster } from "@/components/events/FlyerPoster";
import { eventFlyerAlt, eventListLinkLabel } from "@/lib/events/a11y";
import { isDeadlineKind } from "@/lib/events/content-kind";
import { track } from "@/lib/analytics";
import { saveEventFeedReturn } from "@/lib/events/feed-session";
import { stashEventForDetail } from "@/lib/events/detail-handoff";
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
  const isDeadline = isDeadlineKind(event.contentKind);

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
    stashEventForDetail(event);
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
      // Opens as an overlay (@modal intercepted route); the list keeps its place.
      scroll={false}
      onClick={onOpen}
      onMouseEnter={prefetch}
      onFocus={prefetch}
      aria-label={eventListLinkLabel(event)}
      data-event-id={event.id}
      className={`interactive-focus card-hover group relative isolate flex w-full min-w-0 overflow-hidden rounded-2xl border border-ink/10 bg-canvas transition-[border-color,box-shadow] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:border-ink/30 hover:shadow-cardHover ${
        compact ? "" : "min-h-[6rem] shadow-card"
      }`}
    >
      {/* Time column: typographic anchor at the left edge. The right edge is
         a 2px category-colored rail — magazine column-spine, full-height,
         clipped by the card's rounded corners. Carries the category signal
         without washing the column in tint. */}
      <EventListRowTimeColumn
        startsAt={event.startsAt}
        category={event.category}
        contentKind={event.contentKind}
        compact={compact}
      />

      {/* Flyer pinned whole in a fixed 4:5 slot (Instagram's portrait post).
         Squares, reel covers and landscape posts keep their own shape inside
         it, so nothing is cropped and every row keeps the same rhythm. */}
      {showImage && (
        <div className="my-2 ml-3 flex h-[var(--flyer-max-h)] w-[var(--flyer-max-w)] shrink-0 items-center justify-center self-center [--flyer-max-h:100px] [--flyer-max-w:80px] sm:[--flyer-max-h:110px] sm:[--flyer-max-w:88px]">
          <FlyerPoster
            src={event.imageUrl!}
            alt={eventFlyerAlt(event)}
            sizes="(min-width: 640px) 88px, 80px"
            className="rounded bg-ink/[0.05] shadow-[0_1px_2px_rgba(15,17,21,0.06),0_3px_8px_-2px_rgba(15,17,21,0.08)] ring-1 ring-ink/10"
            onError={() => setImageBroken(true)}
          />
        </div>
      )}

      {/* Text block. Where a pointer can hover, list mode widens the right
         padding to reserve room for the magnetic chevron; touch screens never
         show it, so the title gets that width back. */}
      <div
        className={`flex min-w-0 flex-1 flex-col justify-center gap-1 pl-4 sm:pl-5 ${
          compact
            ? "pr-4 py-2.5"
            : "pr-4 py-3 sm:py-3.5 [@media(hover:hover)]:pr-10"
        }`}
      >
        <h3 className="font-display text-[17px] font-semibold leading-[1.25] tracking-[-0.015em] text-ink line-clamp-2 break-words group-hover:underline group-hover:decoration-ink/30 group-hover:underline-offset-[5px] group-hover:decoration-[1.5px]">
          {event.title}
        </h3>

        <div className="flex min-w-0 items-center gap-x-2 text-[13px] text-muted">
          {isDeadline && !compact && (
            <span className="shrink-0 rounded-full bg-coral/10 px-2 py-0.5 text-[11px] font-medium text-deep-coral">
              Deadline
            </span>
          )}
          {event.hasFreeFood && !compact && !isDeadline && (
            <span className="shrink-0 rounded-full bg-gold/15 px-2 py-0.5 text-[11px] font-medium text-deep-gold">
              Free food
            </span>
          )}
          {event.host ? (
            <span className="min-w-0 truncate">{event.host}</span>
          ) : null}
        </div>

        {event.location?.trim() ? (
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
        ) : null}

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
                …{" "}
                <span className="text-ink underline decoration-ink/30 underline-offset-[3px]">
                  see more
                </span>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Magnetic hover affordance: a feather-light chevron that fades in from
         the right with a small diagonal translate. Reads as "openable" without
         the heaviness of a button. List surface, hover-capable pointers only
         (a tap's sticky hover would flash it over the title). */}
      {!compact && (
        <span
          aria-hidden
          className="pointer-events-none absolute right-3.5 top-1/2 hidden [@media(hover:hover)]:block -translate-x-1 -translate-y-1/2 text-ink/40 opacity-0 transition-[opacity,transform,color] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:translate-x-0 group-hover:text-ink group-hover:opacity-100"
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
