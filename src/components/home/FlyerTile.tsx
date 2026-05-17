"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import type { CampusEvent } from "@/types/event";
import { relativeDay } from "@/lib/dates";
import { CATEGORY_RAIL } from "@/lib/category-colors";
import { track } from "@/lib/analytics";

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
}: {
  event: CampusEvent;
  size: FlyerTileSize;
  className?: string;
  enterDelayMs?: number;
}) {
  const [imageBroken, setImageBroken] = useState(false);
  const showImage = !!event.imageUrl && !imageBroken;

  return (
    <Link
      href={`/events/${event.id}`}
      onClick={() =>
        track("event_open", {
          id: event.id,
          category: event.category,
          surface: "mosaic_tile",
        })
      }
      aria-label={`${event.title} — ${relativeDay(event.startsAt)}`}
      style={{ animationDelay: `${enterDelayMs}ms` }}
      className={`card-hover group relative block overflow-hidden rounded-xl border border-ink/15 bg-canvas aspect-[4/5] md:aspect-auto animate-scale-in ${className}`}
    >
      {showImage ? (
        <Image
          src={event.imageUrl!}
          alt=""
          fill
          unoptimized
          sizes="(max-width: 768px) 100vw, 50vw"
          className="object-cover transition-transform duration-300 group-hover:scale-[1.02]"
          onError={() => setImageBroken(true)}
        />
      ) : (
        <div
          className={`absolute inset-0 ${CATEGORY_RAIL[event.category]} opacity-95`}
          aria-hidden
        />
      )}

      {/* Gradient overlay keeps title readable over any flyer. */}
      <div
        aria-hidden
        className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-ink/90 via-ink/50 to-transparent"
      />

      <div className="absolute inset-x-0 bottom-0 p-3 md:p-4">
        <p
          className={`font-mono uppercase tracking-[0.16em] text-white/80 ${META_CLASSES[size]}`}
        >
          {relativeDay(event.startsAt)}
        </p>
        <p
          className={`mt-1 font-display font-semibold leading-tight tracking-[-0.02em] text-white ${TITLE_CLASSES[size]}`}
        >
          {event.title}
        </p>
      </div>
    </Link>
  );
}
