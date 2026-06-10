"use client";

import Link from "next/link";
import type { CampusEvent } from "@/types/event";
import { EventFlyerImage } from "@/components/events/EventFlyerImage";
import { relativeDay } from "@/lib/dates";
import { eventFlyerAlt, eventTileLinkLabel } from "@/lib/events/a11y";
import { track } from "@/lib/analytics";
import { saveEventFeedReturn } from "@/lib/events/feed-session";
import { useRouter } from "next/navigation";
import { useState } from "react";

export type FlyerTileSize = "large" | "medium" | "small" | "wide";

const TITLE_CLASSES: Record<FlyerTileSize, string> = {
  large: "text-xl md:text-3xl line-clamp-3",
  medium: "text-base md:text-xl line-clamp-2",
  small: "text-sm md:text-[15px] line-clamp-2",
  wide: "text-sm md:text-base line-clamp-2",
};

const META_CLASSES: Record<FlyerTileSize, string> = {
  large: "text-[10px] md:text-[11px]",
  medium: "text-[10px] md:text-[11px]",
  small: "text-[10px]",
  wide: "text-[10px]",
};

export function FlyerTile({
  event,
  size,
  className = "",
  enterDelayMs = 0,
  aspectClassName = "aspect-[4/5] md:aspect-auto",
  decorative = false,
  progressiveBlur = false,
}: {
  event: CampusEvent;
  size: FlyerTileSize;
  className?: string;
  enterDelayMs?: number;
  /** Aspect-ratio utilities for the tile. The mosaic lets its grid drive
   *  height on desktop; the marquee needs a fixed ratio at every breakpoint. */
  aspectClassName?: string;
  /** A repeated tile in a looping marquee: kept out of the tab order and the
   *  accessibility tree so screen readers see each event only once. */
  decorative?: boolean;
  /** Carousel treatment: the flyer reads clean at rest, and the caption rides
   *  in over a frosted (blurred) bottom on hover/focus instead of a persistent
   *  gradient. */
  progressiveBlur?: boolean;
}) {
  const router = useRouter();
  const [imageBroken, setImageBroken] = useState(false);
  const showImage = !!event.imageUrl && !imageBroken;
  const href = `/events/${event.id}`;

  const caption = (
    <>
      <p className={`text-white/85 ${META_CLASSES[size]}`}>
        {relativeDay(event.startsAt)}
      </p>
      <p
        className={`mt-1 font-display font-semibold leading-tight tracking-[-0.02em] text-white ${TITLE_CLASSES[size]}`}
      >
        {event.title}
      </p>
    </>
  );

  return (
    <Link
      href={href}
      onMouseEnter={() => router.prefetch(href)}
      onFocus={() => router.prefetch(href)}
      onClick={(clickEvent) => {
        saveEventFeedReturn(href, {
          eventId: event.id,
          eventTop: clickEvent.currentTarget.getBoundingClientRect().top,
        });
        track("event_open", {
          id: event.id,
          category: event.category,
          surface: "mosaic_tile",
        });
      }}
      aria-label={eventTileLinkLabel(event)}
      aria-hidden={decorative || undefined}
      tabIndex={decorative ? -1 : undefined}
      data-event-id={event.id}
      style={{ animationDelay: `${enterDelayMs}ms` }}
      className={`interactive-focus card-hover group relative block overflow-hidden rounded-xl border border-ink/15 bg-highlander/[0.07] transition-[filter,opacity,border-color] duration-300 hover:border-ink/30 ${aspectClassName} animate-scale-in ${className}`}
    >
      {showImage ? (
        <EventFlyerImage
          src={event.imageUrl!}
          alt={eventFlyerAlt(event)}
          fill
          sizes="(max-width: 768px) 100vw, 50vw"
          className="object-cover"
          onError={() => setImageBroken(true)}
        />
      ) : (
        <div className="absolute inset-0 bg-highlander/[0.07]" aria-hidden />
      )}

      {progressiveBlur ? (
        <>
          {/* Frosted bottom that fades in on hover/focus. A single masked
             backdrop-blur (not a stack of layers) so the frost reads as one
             smooth band with no mid-tile seam. */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 bottom-0 h-[78%] opacity-0 backdrop-blur-md transition-opacity duration-200 ease-out group-hover:opacity-100 group-focus-visible:opacity-100"
            style={{
              maskImage: "linear-gradient(to top, black 55%, transparent 100%)",
              WebkitMaskImage: "linear-gradient(to top, black 55%, transparent 100%)",
            }}
          />
          {/* Soft scrim so the white caption stays legible over any flyer. */}
          <div
            aria-hidden
            className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-ink/70 to-transparent opacity-0 transition-opacity duration-200 ease-out group-hover:opacity-100 group-focus-visible:opacity-100"
          />
          <div className="absolute inset-x-0 bottom-0 p-3 opacity-0 transition-opacity duration-200 ease-out group-hover:opacity-100 group-focus-visible:opacity-100 md:p-4">
            {caption}
          </div>
        </>
      ) : (
        <>
          {/* Gradient overlay keeps title readable over any flyer. */}
          <div
            aria-hidden
            className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-ink/90 via-ink/50 to-transparent"
          />
          <div className="absolute inset-x-0 bottom-0 p-3 md:p-4">{caption}</div>
        </>
      )}
    </Link>
  );
}
