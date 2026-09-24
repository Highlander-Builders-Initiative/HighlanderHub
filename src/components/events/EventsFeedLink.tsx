"use client";

import Link, { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";
import { type ComponentProps, useLayoutEffect } from "react";
import { holdEventsNavSkeleton } from "./events-nav-pending";

type EventsFeedLinkProps = Omit<ComponentProps<typeof Link>, "href" | "prefetch"> & {
  href: string;
};

/** While this link's navigation is in flight, hold the feed's skeleton up. */
function ReportPending() {
  const { pending } = useLinkStatus();
  // A layout effect, so the skeleton lifts in the same commit as the page.
  useLayoutEffect(() => {
    if (pending) return holdEventsNavSkeleton();
  }, [pending]);
  return null;
}

/**
 * An in-app link to /events that opens it the way Luma opens a page: the feed
 * is prefetched while the reader is elsewhere, so the click usually lands at
 * once, and when it is not ready yet the click shows the feed's skeleton
 * straight away (EventsNavSkeleton) instead of leaving the old page up with
 * no sign anything happened. Direct loads never show it: they paint whole.
 *
 * Only the bare /events is prefetched in full, one payload per page view;
 * filtered links (?when=week) still get the skeleton. On the feed itself
 * (and an event over it) neither applies.
 */
export function EventsFeedLink({ href, children, ...props }: EventsFeedLinkProps) {
  const pathname = usePathname();
  const onFeed = pathname === "/events" || !!pathname?.startsWith("/events/");

  return (
    <Link href={href} prefetch={!onFeed && href === "/events" ? true : undefined} {...props}>
      {children}
      {!onFeed && <ReportPending />}
    </Link>
  );
}
