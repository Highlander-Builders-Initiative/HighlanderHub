"use client";

import { useEffect, useRef, useState } from "react";
import type { CampusEvent } from "@/types/event";
import { fetchCalendarEvents } from "@/lib/events/api";

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
  const initialCalendarRangeKey = useRef(calendarRangeKey(calendarRange));
  const [calendarEvents, setCalendarEvents] = useState(initialCalendarEvents);
  const [isCalendarLoading, setIsCalendarLoading] = useState(false);
  const [loadedCalendarRangeKey, setLoadedCalendarRangeKey] = useState(
    initialCalendarRangeKey.current
  );
  const [attemptedCalendarRangeKey, setAttemptedCalendarRangeKey] = useState(
    initialCalendarRangeKey.current
  );
  const currentCalendarRangeKey = calendarRangeKey(calendarRange);

  useEffect(() => {
    setCalendarEvents(initialCalendarEvents);
    setLoadedCalendarRangeKey(initialCalendarRangeKey.current);
    setAttemptedCalendarRangeKey(initialCalendarRangeKey.current);
    setIsCalendarLoading(false);
  }, [initialCalendarEvents]);

  useEffect(() => {
    const key = currentCalendarRangeKey;
    if (key === loadedCalendarRangeKey) {
      setIsCalendarLoading(false);
      return;
    }

    let cancelled = false;
    setAttemptedCalendarRangeKey(key);
    setIsCalendarLoading(true);

    fetchCalendarEvents(calendarRange.start, calendarRange.end)
      .then((nextEvents) => {
        if (cancelled) return;
        setLoadedCalendarRangeKey(key);
        setCalendarEvents(nextEvents);
      })
      .catch(() => {
        if (cancelled) return;
      })
      .finally(() => {
        if (cancelled) return;
        setIsCalendarLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [
    calendarRange.end,
    calendarRange.start,
    currentCalendarRangeKey,
    loadedCalendarRangeKey,
  ]);

  return {
    calendarEvents,
    isCalendarLoading:
      isCalendarLoading ||
      (currentCalendarRangeKey !== loadedCalendarRangeKey &&
        currentCalendarRangeKey !== attemptedCalendarRangeKey),
  };
}
