import type { CampusEvent } from "@/types/event";
import { pacificDayKey } from "@/lib/dates";

function monthKeyFromDayKey(dayKey: string): string {
  return dayKey.slice(0, 7);
}

function calendarEventsInMonth(
  calendarEvents: CampusEvent[],
  monthKey: string
): CampusEvent[] {
  return calendarEvents.filter(
    (event) => monthKeyFromDayKey(pacificDayKey(event.startsAt)) === monthKey
  );
}

/**
 * True when `dayKey` is the last day with events in its month (per calendar data)
 * and every calendar event on that day is already in the feed. Used to hide the
 * paginated "More below" hint after jumping to the end of the visible month.
 */
export function calendarJumpEndsAtLoadedBoundary(
  merged: CampusEvent[],
  calendarEvents: CampusEvent[],
  dayKey: string
): boolean {
  const monthKey = monthKeyFromDayKey(dayKey);
  const monthEvents = calendarEventsInMonth(calendarEvents, monthKey);

  const maxDayInMonth = monthEvents.reduce((max, event) => {
    const key = pacificDayKey(event.startsAt);
    return key > max ? key : max;
  }, "");

  if (!maxDayInMonth || dayKey < maxDayInMonth) return false;

  const mergedIds = new Set(merged.map((event) => event.id));
  const eventsOnTargetDay = monthEvents.filter(
    (event) => pacificDayKey(event.startsAt) === dayKey
  );

  return (
    eventsOnTargetDay.length > 0 &&
    eventsOnTargetDay.every((event) => mergedIds.has(event.id))
  );
}
