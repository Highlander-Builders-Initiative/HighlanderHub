"use client";

import Link from "next/link";
import type { CampusEvent } from "@/types/event";
import { EventFlyerImage } from "@/components/events/EventFlyerImage";
import { relativeDay } from "@/lib/dates";
import { eventFlyerAlt, eventTileLinkLabel } from "@/lib/events/a11y";
import { track } from "@/lib/analytics";
import { saveEventFeedReturn } from "@/lib/events/feed-session";
import { stashEventForDetail } from "@/lib/events/detail-handoff";
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

// A flyer within ~8% of its tile's shape fills the tile edge to edge (the trim
// is imperceptible). Any other shape (squares, reel covers, landscape posts)
// is pinned whole on the tile instead of being cut down to fit it.
const FILL_TOLERANCE = 0.08;

export function FlyerTile({
  event,
  size,
  className = "",
  enterDelayMs = 0,
  aspectClassName = "aspect-[4/5] md:aspect-auto",
  sizes = "(max-width: 768px) 100vw, 50vw",
  decorative = false,
  hoverCaption = false,
}: {
  event: CampusEvent;
  size: FlyerTileSize;
  className?: string;
  enterDelayMs?: number;
  /** Aspect-ratio utilities for the tile. The mosaic lets its grid drive
   *  height on desktop; the marquee needs a fixed ratio at every breakpoint. */
  aspectClassName?: string;
  /** Rendered tile widths, so the browser fetches a flyer no larger than needed. */
  sizes?: string;
  /** A repeated tile in a looping marquee: kept out of the tab order and the
   *  accessibility tree so screen readers see each event only once. */
  decorative?: boolean;
  /** Carousel treatment: the flyer reads clean at rest, and the caption fades
   *  in over a soft scrim on hover/focus instead of a persistent gradient. */
  hoverCaption?: boolean;
}) {
  const router = useRouter();
  const [imageBroken, setImageBroken] = useState(false);
  const [pinned, setPinned] = useState(false);
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
      // Opens as an overlay (@modal intercepted route); the page keeps its place.
      scroll={false}
      onMouseEnter={() => router.prefetch(href)}
      onFocus={() => router.prefetch(href)}
      onClick={(clickEvent) => {
        stashEventForDetail(event);
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
          width={1000}
          height={1250}
          sizes={sizes}
          className={
            pinned
              ? "absolute inset-0 m-auto h-auto max-h-[calc(100%-1.5rem)] w-auto max-w-[calc(100%-1.5rem)] rounded-md shadow-[0_1px_2px_rgba(15,17,21,0.08),0_4px_12px_-2px_rgba(15,17,21,0.08)] ring-1 ring-ink/10"
              : "absolute inset-0 h-full w-full object-cover"
          }
          onLoad={(img) => {
            const tile = img.parentElement;
            if (!tile?.clientHeight || !img.naturalHeight) return;
            const flyerRatio = img.naturalWidth / img.naturalHeight;
            const tileRatio = tile.clientWidth / tile.clientHeight;
            setPinned(Math.abs(Math.log(flyerRatio / tileRatio)) > FILL_TOLERANCE);
          }}
          onError={() => setImageBroken(true)}
        />
      ) : (
        <div className="absolute inset-0 bg-highlander/[0.07]" aria-hidden />
      )}

      {hoverCaption ? (
        <>
          {/* Soft scrim so the white caption stays legible over any flyer.
             No backdrop-blur here: Chrome never painted it inside the
             marquee's transformed, masked tiles, while Safari did — blurring
             most of the flyer and flickering as the strip moved. */}
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
