import type { Metadata } from "next";
import { Masthead } from "@/components/layout/Masthead";
import { EventsBrowser } from "@/components/events/EventsBrowser";
import { Footer } from "@/components/layout/Footer";
import {
  getCalendarEvents,
  getEventsPage,
  getEventsSummary,
} from "@/lib/events";
import {
  pacificCalendarGridRange,
  pacificTodayKey,
  startOfPacificMonthKey,
} from "@/lib/dates";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Events · Highlander Hub",
  description:
    "Browse and filter campus and club events at UC Riverside and around the city.",
};

export default async function EventsPage() {
  const calendarRange = pacificCalendarGridRange(
    startOfPacificMonthKey(pacificTodayKey())
  );
  const [initialPage, calendarEvents, summary] = await Promise.all([
    getEventsPage(),
    getCalendarEvents({
      startDayKey: calendarRange.start,
      endDayKey: calendarRange.end,
    }),
    getEventsSummary(),
  ]);
  const events = initialPage.events;

  return (
    <main className="min-h-screen bg-canvas">
      <Masthead position="static" variant="solid" hideNavOnDesktop />

      <EventsBrowser
        events={events}
        calendarEvents={calendarEvents}
        summary={summary}
        initialHasMore={initialPage.hasMore}
        initialNextOffset={initialPage.nextOffset}
      />

      <Footer />
    </main>
  );
}
