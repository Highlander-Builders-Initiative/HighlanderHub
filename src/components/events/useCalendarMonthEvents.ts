"use client";

import { useEffect, useRef, useState } from "react";
import type { CampusEvent } from "@/types/event";
import { fetchCalendarEvents } from "@/lib/events-api";

type CalendarRange = {
  start: string;
  end: string;
};

type UseCalendarMonthEventsArgs = {
  initialCalendarEvents: CampusEvent[];
  calendarRange: CalendarRange;
};

function calendarRangeKey(range: CalendarRange) {
  return `${range.start}:${range.end}`;
}

export function useCalendarMonthEvents({
  initialCalendarEvents,
  calendarRange,
}: UseCalendarMonthEventsArgs) {
  const [calendarEvents, setCalendarEvents] = useState(initialCalendarEvents);
  const [isCalendarLoading, setIsCalendarLoading] = useState(false);
  const loadedCalendarRangeKey = useRef(calendarRangeKey(calendarRange));

  useEffect(() => {
    setCalendarEvents(initialCalendarEvents);
    setIsCalendarLoading(false);
  }, [initialCalendarEvents]);

  useEffect(() => {
    const key = calendarRangeKey(calendarRange);
    if (key === loadedCalendarRangeKey.current) {
      setIsCalendarLoading(false);
      return;
    }

    let cancelled = false;
    setIsCalendarLoading(true);

    fetchCalendarEvents(calendarRange.start, calendarRange.end)
      .then((nextEvents) => {
        if (cancelled) return;
        loadedCalendarRangeKey.current = key;
        setCalendarEvents(nextEvents);
      })
      .catch(() => {
        if (cancelled) return;
        setCalendarEvents([]);
      })
      .finally(() => {
        if (cancelled) return;
        setIsCalendarLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [calendarRange]);

  return { calendarEvents, isCalendarLoading };
}
