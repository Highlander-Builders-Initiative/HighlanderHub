"use client";

import { usePathname } from "next/navigation";
import {
  EVENT_DETAIL_FLYER_FRAME_CLASS,
  EVENT_DETAIL_MOBILE_FLYER_CLASS,
  EVENT_MODAL_ASIDE_CLASS,
  EVENT_MODAL_CONTAINER_CLASS,
  EVENT_MODAL_FLYER_GRID_CLASS,
  EventDetailView,
} from "@/components/events/EventDetailView";
import { peekEventForDetail } from "@/lib/events/detail-handoff";

function eventIdFromPath(pathname: string | null): string | null {
  const segment = pathname?.split("/").filter(Boolean)[1];
  if (!segment) return null;
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

function Bar({ className }: { className: string }) {
  return <span aria-hidden className={`block rounded-full bg-ink/10 ${className}`} />;
}

/** A bar vertically centered in a box sized to one line of the real text. */
function LineBar({ line, bar }: { line: string; bar: string }) {
  return (
    <span aria-hidden className={`flex items-center ${line}`}>
      <Bar className={bar} />
    </span>
  );
}

/**
 * Shared by intercepted cards and direct loads. In-app cards hand off their
 * event immediately; refreshes and shared links use the same compact skeleton.
 */
function EventModalSkeleton() {
  return (
    <div className={EVENT_MODAL_CONTAINER_CLASS}>
      <p className="sr-only" role="status">
        Loading event
      </p>

      <div className={EVENT_DETAIL_MOBILE_FLYER_CLASS}>
        <div className="relative aspect-[4/5] w-full bg-ink/[0.04]" />
      </div>

      <div className="flex flex-wrap items-center gap-2 md:pr-12">
        <Bar className="h-[22px] w-20" />
        <Bar className="h-[22px] w-12" />
      </div>
      <div className="mt-3 max-w-3xl md:mt-5 md:pr-12">
        <LineBar
          line="h-[30px] sm:h-[38px]"
          bar="h-[22px] w-full sm:h-[28px] sm:w-3/4"
        />
      </div>

      <div className={EVENT_MODAL_FLYER_GRID_CLASS}>
        <div className={EVENT_MODAL_ASIDE_CLASS}>
          <div className={EVENT_DETAIL_FLYER_FRAME_CLASS}>
            <div className="relative aspect-[4/5] w-full bg-ink/[0.04]" />
          </div>
        </div>

        <div className="min-w-0">
          <div className="space-y-3">
            <LineBar line="h-[25px]" bar="h-4 w-44" />
            <LineBar line="h-[21px]" bar="h-3 w-52 max-w-full" />
            <LineBar line="h-[22px]" bar="h-3.5 w-48 max-w-full" />
          </div>
          <div className="mt-6 max-w-prose md:mt-10">
            {["w-full", "w-11/12", "w-full", "w-2/3"].map((width, i) => (
              <LineBar key={i} line="h-[26px]" bar={`h-3.5 ${width}`} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function EventModalDetailLoading() {
  const eventId = eventIdFromPath(usePathname());
  const handedOff = eventId ? peekEventForDetail(eventId) : null;

  if (handedOff) return <EventDetailView event={handedOff} variant="modal" />;
  return <EventModalSkeleton />;
}
