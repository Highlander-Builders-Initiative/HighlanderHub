import { Suspense, type ReactNode } from "react";
import { EventModal } from "@/components/events/EventModal";
import EventsPage from "../page";
import EventsLoading from "../loading";

/** Refreshes and shared links use the same card shell as in-app navigation. */
export default function EventDetailLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <Suspense fallback={<EventsLoading />}>
        <EventsPage searchParams={Promise.resolve({})} />
      </Suspense>
      <EventModal standalone>{children}</EventModal>
    </>
  );
}
