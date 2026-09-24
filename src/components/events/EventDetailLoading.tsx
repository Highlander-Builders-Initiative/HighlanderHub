"use client";

import { usePathname } from "next/navigation";
import {
  EVENT_DETAIL_FLYER_CLASS,
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
  return <span aria-hidden className={`skeleton block rounded-full bg-ink/10 ${className}`} />;
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
 * The overlay's loading state for in-app opens. Cards hand off their event,
 * so it renders at once; anything else (a link with no handoff) shows this
 * compact skeleton. Direct loads have no loading state: they paint whole.
 */
function EventModalSkeleton() {
  return (
    <div className={EVENT_MODAL_CONTAINER_CLASS}>
      <p className="sr-only" role="status">
        Loading event
      </p>

      {/* The same 4:5 placeholder the real flyer holds until it loads. */}
      <div className={EVENT_DETAIL_MOBILE_FLYER_CLASS}>
        <div className={`flyer-poster skeleton ${EVENT_DETAIL_FLYER_CLASS}`} />
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
      {/* The "By" line: club picture and names. */}
      <div className="mt-3 flex h-[23px] items-center gap-2 md:mt-4">
        <Bar className="h-5 w-5 shrink-0" />
        <Bar className="h-3.5 w-48 max-w-full" />
      </div>

      <div className={EVENT_MODAL_FLYER_GRID_CLASS}>
        <div className={EVENT_MODAL_ASIDE_CLASS}>
          <div className={`flyer-poster skeleton ${EVENT_DETAIL_FLYER_CLASS}`} />
        </div>

        <div className="min-w-0">
          {/* When and where: icon rows, as in the view. */}
          <div className="space-y-3.5">
            <div className="flex gap-3">
              <LineBar line="h-6 w-5 shrink-0 justify-center" bar="h-[18px] w-[18px]" />
              <div className="min-w-0 flex-1">
                <LineBar line="h-6" bar="h-4 w-44" />
                <LineBar line="mt-0.5 h-[21px]" bar="h-3 w-52 max-w-full" />
              </div>
            </div>
            <div className="flex gap-3">
              <LineBar line="h-6 w-5 shrink-0 justify-center" bar="h-[18px] w-[18px]" />
              <LineBar line="h-6 min-w-0 flex-1" bar="h-3.5 w-48 max-w-full" />
            </div>
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
