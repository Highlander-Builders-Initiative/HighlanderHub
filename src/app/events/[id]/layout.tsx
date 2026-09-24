import type { ReactNode } from "react";
import { EventModal } from "@/components/events/EventModal";
import EventsPage from "../page";

/**
 * Refreshes and shared links use the same card shell as in-app navigation.
 * No loading fallback here or in the route: a direct load waits for the feed
 * and the event, then paints both whole, so a refresh keeps the page as it
 * was instead of flashing placeholders. In-app opens never reach this route;
 * the @modal overlay intercepts them and has its own loading state.
 */
export default function EventDetailLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <EventsPage searchParams={Promise.resolve({})} />
      <EventModal standalone>{children}</EventModal>
    </>
  );
}
