import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Masthead } from "@/components/layout/Masthead";
import { EventsBrowser } from "@/components/events/EventsBrowser";
import {
  FEED_VIEW_COOKIE,
  coerceCategoryParam,
  coerceDayWindowParam,
  coerceFeedView,
} from "@/components/events/events-filters";
import { Footer } from "@/components/layout/Footer";
import {
  getCalendarEvents,
  getEventFilterCountSource,
  getEventsPage,
  getEventsSummary,
} from "@/lib/events";
import { shareCalendarEvents } from "@/lib/events/share-calendar-events";
import {
  pacificCalendarGridRange,
  pacificTodayKey,
  startOfPacificMonthKey,
} from "@/lib/dates";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Events",
  description:
    "Browse and filter campus and club events at UC Riverside.",
};

type SearchParam = string | string[] | undefined;
function firstParam(raw: SearchParam): string | undefined {
  return Array.isArray(raw) ? raw[0] : raw;
}

type EventsPageProps = {
  searchParams: Promise<{ [key: string]: SearchParam }>;
};

export default async function EventsPage({ searchParams }: EventsPageProps) {
  const params = await searchParams;
  const initialView = coerceFeedView((await cookies()).get(FEED_VIEW_COOKIE)?.value);
  const initialFilters = {
    category: coerceCategoryParam(firstParam(params.cat)),
    query: firstParam(params.q) ?? "",
    dayWindow: coerceDayWindowParam(firstParam(params.when)),
  };
  const calendarRange = pacificCalendarGridRange(
    startOfPacificMonthKey(pacificTodayKey())
  );
  const [initialPage, calendarEvents, summary, countSource] =
    await Promise.all([
      getEventsPage(initialFilters),
      getCalendarEvents({
        startDayKey: calendarRange.start,
        endDayKey: calendarRange.end,
      }),
      getEventsSummary(),
      getEventFilterCountSource(),
    ]);
  const { events, filterCountSource } = shareCalendarEvents(calendarEvents, {
    events: initialPage.events,
    filterCountSource: countSource,
  });

  return (
    <main className="min-h-screen bg-surface">
      <Masthead position="static" variant="solid" />

      <EventsBrowser
        events={events}
        calendarEvents={calendarEvents}
        summary={summary}
        filterCountSource={filterCountSource}
        initialHasMore={initialPage.hasMore}
        initialNextOffset={initialPage.nextOffset}
        initialFilters={initialFilters}
        initialView={initialView}
      />

      {/* Page-edge softener: a quiet fade at the very bottom of the
          viewport so the long-scroll feed never ends on a hard line.
          Page-edge structural treatment, not decorative chrome; scoped
          to /events where the long scroll warrants it. */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-x-0 bottom-0 z-10 h-10 bg-gradient-to-t from-surface via-surface/30 to-transparent sm:h-12"
        style={{
          backdropFilter: "blur(1.25px)",
          WebkitBackdropFilter: "blur(1.25px)",
          maskImage:
            "linear-gradient(to top, black 40%, transparent 100%)",
          WebkitMaskImage:
            "linear-gradient(to top, black 40%, transparent 100%)",
        }}
      />

      <Footer />
    </main>
  );
}
