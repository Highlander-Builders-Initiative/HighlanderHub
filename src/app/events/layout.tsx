import type { ReactNode } from "react";
import { EventsFeedDataProvider } from "@/components/events/EventsFeedData";
import {
  getCalendarEvents,
  getEventFilterCountSource,
  getEventsUpcomingThisWeek,
} from "@/lib/events";
import { shareCalendarEvents } from "@/lib/events/share-calendar-events";
import {
  pacificCalendarGridRange,
  pacificTodayKey,
  startOfPacificMonthKey,
} from "@/lib/dates";

/**
 * Loads the feed's filter-independent data once per visit. Choosing a filter
 * replaces the URL's search params, which re-renders the page (its first page
 * of events) but not this layout, so the month calendar and every upcoming
 * event are not sent again. /events/[id] renders the feed under its card and
 * reads the same data.
 */
export default async function EventsLayout({ children }: { children: ReactNode }) {
  const calendarRange = pacificCalendarGridRange(
    startOfPacificMonthKey(pacificTodayKey())
  );
  const [calendarEvents, upcomingThisWeek, countSource] = await Promise.all([
    getCalendarEvents({
      startDayKey: calendarRange.start,
      endDayKey: calendarRange.end,
    }),
    getEventsUpcomingThisWeek(),
    getEventFilterCountSource(),
  ]);

  return (
    <EventsFeedDataProvider
      value={{
        calendarEvents,
        filterCountSource: shareCalendarEvents(calendarEvents, countSource),
        summary: { upcomingThisWeek },
      }}
    >
      {children}
    </EventsFeedDataProvider>
  );
}
