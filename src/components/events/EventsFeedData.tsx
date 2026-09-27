"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { CampusEvent } from "@/types/event";
import type { EventFilterCountSource } from "@/types/events-feed";

/**
 * The feed's data that no filter changes. The events layout provides it: a
 * layout does not re-render when only the search params change, so a filter
 * change sends the new first page instead of every upcoming event again.
 */
export type EventsFeedData = {
  calendarEvents: CampusEvent[];
  filterCountSource: EventFilterCountSource[];
  summary: { upcomingThisWeek: number };
};

const EventsFeedDataContext = createContext<EventsFeedData | undefined>(undefined);

export function EventsFeedDataProvider({
  value,
  children,
}: {
  value: EventsFeedData;
  children: ReactNode;
}) {
  return (
    <EventsFeedDataContext.Provider value={value}>
      {children}
    </EventsFeedDataContext.Provider>
  );
}

export function useEventsFeedData(): EventsFeedData {
  const context = useContext(EventsFeedDataContext);
  if (!context) {
    throw new Error("useEventsFeedData must be used within the events layout");
  }
  return context;
}
