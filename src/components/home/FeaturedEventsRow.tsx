"use client";

import Link from "next/link";
import { useState } from "react";
import type { CampusEvent } from "@/types/event";
import { formatTimeRange } from "@/lib/dates";
import { FiCalendar, FiMapPin, FiGift, FiArrowRight } from "react-icons/fi";
import { stashEventForDetail } from "@/lib/events/detail-handoff";
import { track } from "@/lib/analytics";
import { EventFlyerImage } from "@/components/events/EventFlyerImage";

export function FeaturedEventsRow({ events }: { events: CampusEvent[] }) {
  const [imageErrors, setImageErrors] = useState<Record<string, boolean>>({});

  // Show up to 6 featured upcoming events
  const featured = events.slice(0, 6);

  if (featured.length === 0) return null;

  return (
    <section className="relative bg-slate-50/60 py-14 md:py-20 border-y border-slate-200/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        {/* Section Header */}
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-200/60 bg-blue-50/70 px-3 py-1 text-xs font-semibold text-blue-700">
              UPCOMING AT UCR
            </div>
            <h2 className="mt-2 font-display text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl md:text-4xl">
              What&apos;s happening
            </h2>
            <p className="mt-1 text-sm text-slate-600 sm:text-base">
              Club workshops, campus socials, guest talks, and activities.
            </p>
          </div>

          <Link
            href="/events"
            className="group inline-flex items-center gap-2 text-sm font-medium text-blue-600 transition-colors hover:text-blue-800"
          >
            <span>View calendar & full list</span>
            <FiArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </Link>
        </div>

        {/* Event Cards Grid */}
        <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {featured.map((event) => {
            const hasImage = !!event.imageUrl && !imageErrors[event.id];
            const timeLabel = formatTimeRange(event.startsAt, event.endsAt);

            return (
              <Link
                key={event.id}
                href={`/events/${event.id}`}
                scroll={false}
                onClick={() => {
                  stashEventForDetail(event);
                  track("event_open", {
                    id: event.id,
                    category: event.category,
                    surface: "list_card",
                  });
                }}
                className="group relative flex flex-col overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-blue-300 hover:shadow-md"
              >
                {/* Flyer Thumbnail or Gradient Header */}
                <div className="relative aspect-[16/9] w-full overflow-hidden bg-slate-100">
                  {hasImage ? (
                    <EventFlyerImage
                      src={event.imageUrl!}
                      alt={event.title}
                      fill
                      sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
                      className="object-cover transition-transform duration-300 group-hover:scale-105"
                      onError={() =>
                        setImageErrors((prev) => ({ ...prev, [event.id]: true }))
                      }
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-blue-900 via-blue-800 to-indigo-950 p-4 text-center text-white">
                      <span className="font-display text-sm font-semibold opacity-85 line-clamp-2">
                        {event.host || "UCR Campus Event"}
                      </span>
                    </div>
                  )}

                  {/* Category Pill Over Image */}
                  <div className="absolute left-3 top-3 flex flex-wrap gap-1.5 z-10">
                    <span className="rounded-full bg-black/60 px-2.5 py-0.5 text-[11px] font-semibold text-white backdrop-blur-md capitalize">
                      {event.category.replace("_", " ")}
                    </span>
                    {event.hasFreeFood && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/90 px-2 py-0.5 text-[11px] font-bold text-white backdrop-blur-md shadow-sm">
                        <FiGift className="h-3 w-3" />
                        Free Food
                      </span>
                    )}
                  </div>
                </div>

                {/* Event Body */}
                <div className="flex flex-1 flex-col justify-between p-4 sm:p-5">
                  <div>
                    {/* Time & Host */}
                    <div className="flex items-center justify-between gap-2 text-xs text-slate-600">
                      <span className="inline-flex items-center gap-1 font-medium text-blue-600">
                        <FiCalendar className="h-3.5 w-3.5 shrink-0" />
                        {timeLabel}
                      </span>
                      {event.host && (
                        <span className="truncate font-medium text-slate-600 max-w-[140px]">
                          {event.host}
                        </span>
                      )}
                    </div>

                    {/* Title */}
                    <h3 className="mt-2 font-display text-base font-bold text-slate-900 line-clamp-2 transition-colors group-hover:text-blue-600">
                      {event.title}
                    </h3>

                    {/* Location */}
                    {event.location && (
                      <p className="mt-1.5 inline-flex items-center gap-1 text-xs text-slate-600 line-clamp-1">
                        <FiMapPin className="h-3 w-3 shrink-0 text-slate-600" />
                        {event.location}
                      </p>
                    )}
                  </div>

                  {/* Card Bottom CTA */}
                  <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-xs font-semibold text-blue-600 group-hover:text-blue-700">
                    <span>View details</span>
                    <FiArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}
