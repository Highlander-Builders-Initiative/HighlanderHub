"use client";

import { Masthead } from "@/components/layout/Masthead";
import { EventsBrowserSkeleton } from "./EventsBrowserSkeleton";
import { useEventsNavPending } from "./events-nav-pending";

/**
 * The /events page's skeleton, drawn over the current page while an in-app
 * link to the feed waits on its data (EventsFeedLink). Same masthead and grid
 * as the feed, so when the page lands only the rows change. It fades in after
 * a beat (.nav-skeleton), so a navigation that is nearly instant never
 * flashes it.
 */
export function EventsNavSkeleton() {
  const pending = useEventsNavPending();
  if (!pending) return null;

  return (
    <div
      data-events-nav-skeleton
      className="nav-skeleton fixed inset-0 z-[60] overflow-hidden bg-surface"
    >
      <Masthead position="static" variant="solid" activePath="/events" />
      <EventsBrowserSkeleton />
    </div>
  );
}
