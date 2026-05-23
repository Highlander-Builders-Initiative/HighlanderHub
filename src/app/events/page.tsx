import type { Metadata } from "next";
import { Masthead } from "@/components/layout/Masthead";
import { EventsBrowser } from "@/components/events/EventsBrowser";
import { SubmitEventCta } from "@/components/events/SubmitEventCta";
import { Footer } from "@/components/layout/Footer";
import { getEventsPage, getEventsSummary } from "@/lib/events";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Events · Highlander Hub",
  description:
    "Browse and filter campus and club events at UC Riverside and around the city.",
};

export default async function EventsPage() {
  const [initialPage, summary] = await Promise.all([
    getEventsPage(),
    getEventsSummary(),
  ]);
  const events = initialPage.events;

  return (
    <main className="min-h-screen bg-canvas">
      <Masthead position="static" variant="solid" />

      {/* Page header */}
      <section className="border-b border-ink/10">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 pt-6 pb-5 sm:px-6 md:flex-row md:items-end md:justify-between md:pt-14 md:pb-8">
          <div>
            <h1 className="font-display text-3xl font-semibold leading-[1.05] tracking-[-0.03em] text-ink md:text-5xl">
              Events
            </h1>
            <p className="mt-2 max-w-xl text-base text-ink/75 md:mt-3">
              Discover {summary.total} campus gatherings, with {summary.upcomingThisWeek} happening this week and {summary.freeFood} serving free food.
            </p>
          </div>
          <div className="flex flex-col items-stretch gap-4 sm:items-start md:items-end md:gap-5">
            <SubmitEventCta surface="events_header" />
          </div>
        </div>
      </section>

      <EventsBrowser
        events={events}
        initialHasMore={initialPage.hasMore}
        initialNextOffset={initialPage.nextOffset}
      />

      <Footer />
    </main>
  );
}
