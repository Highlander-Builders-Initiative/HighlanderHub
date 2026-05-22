"use client";

import Image from "next/image";
import Link from "next/link";
import { type MouseEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { CampusEvent } from "@/types/event";
import { formatTime, relativeDay } from "@/lib/dates";
import { track } from "@/lib/analytics";
import { saveEventFeedReturn } from "@/lib/event-feed-session";
import { CategoryBadge } from "../ui/CategoryBadge";

export function EventCard({
  event,
  compact = false,
  loadedCount,
}: {
  event: CampusEvent;
  compact?: boolean;
  loadedCount?: number;
}) {
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

  if (showImage) {
    return (
      <ImageCard
        event={event}
        href={href}
        onPrefetch={() => router.prefetch(href)}
        onImageError={() => setImageBroken(true)}
        onOpen={onOpen}
      />
    );
  }
  return (
    <TextCard
      event={event}
      href={href}
      onPrefetch={() => router.prefetch(href)}
      onOpen={onOpen}
    />
  );
}

function flyerAlt(event: CampusEvent) {
  return `Flyer for ${event.title}`;
}

function ImageCard({
  event,
  href,
  onPrefetch,
  onImageError,
  onOpen,
}: {
  event: CampusEvent;
  href: string;
  onPrefetch: () => void;
  onImageError: () => void;
  onOpen: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  return (
    <Link
      href={href}
      onClick={onOpen}
      onMouseEnter={onPrefetch}
      onFocus={onPrefetch}
      aria-label={`${event.title}, ${relativeDay(event.startsAt)} at ${formatTime(event.startsAt)}`}
      data-event-id={event.id}
      className="interactive-focus card-hover group relative block w-full overflow-hidden rounded-xl border border-ink/15 bg-canvas aspect-[4/5]"
    >
      <Image
        src={event.imageUrl!}
        alt={flyerAlt(event)}
        fill
        sizes="(max-width: 768px) 100vw, (max-width: 1024px) 50vw, 33vw"
        className="object-cover transition-transform duration-300 group-hover:scale-[1.02]"
        onError={onImageError}
      />

      <div
        aria-hidden
        className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-ink/90 via-ink/50 to-transparent"
      />

      <div className="absolute inset-x-0 bottom-0 p-3 md:p-4">
        <p className="text-[12px] text-white/85 md:text-[13px]">
          {relativeDay(event.startsAt)} · {formatTime(event.startsAt)}
        </p>
        <p className="mt-1 font-display text-base font-semibold leading-tight tracking-[-0.02em] text-white line-clamp-2 md:text-lg">
          {event.title}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <CategoryBadge category={event.category} variant="overlay" />
          {event.isFree && (
            <span className="inline-flex items-center rounded-full bg-white/15 px-2.5 py-0.5 text-[11px] font-medium text-white backdrop-blur-sm">
              Free
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

function TextCard({
  event,
  href,
  onPrefetch,
  onOpen,
}: {
  event: CampusEvent;
  href: string;
  onPrefetch: () => void;
  onOpen: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  return (
    <Link
      href={href}
      onClick={onOpen}
      onMouseEnter={onPrefetch}
      onFocus={onPrefetch}
      aria-label={`${event.title}, ${relativeDay(event.startsAt)} at ${formatTime(event.startsAt)}`}
      data-event-id={event.id}
      className="interactive-focus card-hover group relative flex h-full w-full min-w-0 overflow-hidden rounded-xl border border-ink/15 bg-canvas"
    >
      <div className="flex min-w-0 flex-1 items-stretch">
        <div className="flex min-w-0 flex-1 flex-col justify-center gap-1 px-4 py-3 sm:px-5 sm:py-4">
          <div className="flex min-w-0 items-center gap-2 text-[13px] text-muted">
            <span className="shrink-0">{formatTime(event.startsAt)}</span>
            <span className="shrink-0 text-ink/20">·</span>
            <span className="min-w-0 truncate">{event.location}</span>
          </div>

          <h3 className="font-display text-[17px] font-semibold leading-[1.2] tracking-[-0.015em] text-ink line-clamp-2 break-words sm:text-[18px]">
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
      </div>
    </Link>
  );
}
