"use client";

import { useCallback, useEffect, useState } from "react";
import type { CampusEvent } from "@/types/event";
import { fetchCalendarEvents } from "@/lib/events/api";

type CalendarRange = { start: string; end: string };
type UseCalendarMonthEventsArgs = {
  initialCalendarEvents: CampusEvent[];
  calendarRange: CalendarRange;
};
const EMPTY_EVENTS: CampusEvent[] = [];

type MonthState = {
  key: string;
  status: "loading" | "success" | "error";
  events: CampusEvent[];
};

export function useCalendarMonthEvents({
  initialCalendarEvents,
  calendarRange,
}: UseCalendarMonthEventsArgs) {
  const key = `${calendarRange.start}:${calendarRange.end}`;
  const [initialKey] = useState(key);
  const serverEvents = key === initialKey ? initialCalendarEvents : null;
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<MonthState>({
    key, status: "success", events: initialCalendarEvents,
  });
  const retryCalendar = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    if (serverEvents) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- starting an external range request
    setState({ key, status: "loading", events: [] });
    fetchCalendarEvents(calendarRange.start, calendarRange.end)
      .then((events) => {
        if (!cancelled) setState({ key, status: "success", events });
      })
      .catch(() => {
        if (!cancelled) setState({ key, status: "error", events: [] });
      });
    return () => { cancelled = true; };
  }, [key, calendarRange.start, calendarRange.end, serverEvents, attempt]);

  const current = state.key === key;
  return {
    calendarEvents: serverEvents ?? (current && state.status === "success" ? state.events : EMPTY_EVENTS),
    isCalendarLoading: !serverEvents && (!current || state.status === "loading"),
    calendarError: !serverEvents && current && state.status === "error",
    retryCalendar,
  };
}
