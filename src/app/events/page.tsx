import type { Metadata } from "next";
import { Masthead } from "@/components/layout/Masthead";
import { EventsBrowser } from "@/components/events/EventsBrowser";
import {
  coerceCategoryParam,
  coerceDayWindowParam,
} from "@/components/events/events-filters";
import { Footer } from "@/components/layout/Footer";
import {
  getCalendarEvents,
  getEventFilterCountSource,
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

type SearchParam = string | string[] | undefined;
function firstParam(raw: SearchParam): string | undefined {
  return Array.isArray(raw) ? raw[0] : raw;
}

type EventsPageProps = {
  searchParams: { [key: string]: SearchParam };
};

export default async function EventsPage({ searchParams }: EventsPageProps) {
  const calendarRange = pacificCalendarGridRange(
    startOfPacificMonthKey(pacificTodayKey())
  );
  const [initialPage, calendarEvents, summary, filterCountSource] =
    await Promise.all([
      getEventsPage(),
      getCalendarEvents({
        startDayKey: calendarRange.start,
        endDayKey: calendarRange.end,
      }),
      getEventsSummary(),
      getEventFilterCountSource(),
    ]);
  const events = initialPage.events;

  const initialFilters = {
    category: coerceCategoryParam(firstParam(searchParams.cat)),
    query: firstParam(searchParams.q) ?? "",
    dayWindow: coerceDayWindowParam(firstParam(searchParams.when)),
  };

  return (
    <main className="min-h-screen bg-canvas">
      <Masthead position="static" variant="solid" hideNavOnDesktop />

      <EventsBrowser
        events={events}
        calendarEvents={calendarEvents}
        summary={summary}
        filterCountSource={filterCountSource}
        initialHasMore={initialPage.hasMore}
        initialNextOffset={initialPage.nextOffset}
        initialFilters={initialFilters}
      />

      {/* Page-edge softener: a fade plus soft backdrop-blur masks the bottom
          of the viewport so the long-scroll feed never ends on a hard line.
          A page-edge structural treatment, not decorative chrome; scoped to
          /events where the long scroll warrants it. */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-x-0 bottom-0 z-10 h-16 bg-gradient-to-t from-canvas via-canvas/55 to-transparent sm:h-20"
        style={{
          backdropFilter: "blur(3px)",
          WebkitBackdropFilter: "blur(3px)",
          maskImage:
            "linear-gradient(to top, black 55%, transparent 100%)",
          WebkitMaskImage:
            "linear-gradient(to top, black 55%, transparent 100%)",
        }}
      />

      <Footer />
    </main>
  );
}
