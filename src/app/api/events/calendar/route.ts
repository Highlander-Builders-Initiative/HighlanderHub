import { NextResponse } from "next/server";
import { getCalendarEvents } from "@/lib/events";
import {
  CALENDAR_GRID_DAYS,
  addPacificDays,
  pacificCalendarGridRange,
  pacificTodayKey,
  parsePacificDateTimeInput,
  startOfPacificMonthKey,
} from "@/lib/dates";

export const dynamic = "force-dynamic";

function readDayKey(value: string | null, fallback: string): string {
  // A well-formed but impossible date (month 13) is as unusable as a malformed one.
  return value &&
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    parsePacificDateTimeInput(`${value}T00:00`)
    ? value
    : fallback;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const defaultRange = pacificCalendarGridRange(
    startOfPacificMonthKey(pacificTodayKey())
  );
  const startDayKey = readDayKey(searchParams.get("start"), defaultRange.start);
  const endDayKey = readDayKey(searchParams.get("end"), defaultRange.end);
  // At most one grid per request: every read pages through all rows in range.
  const lastDayKey = addPacificDays(startDayKey, CALENDAR_GRID_DAYS - 1);

  const events = await getCalendarEvents({
    startDayKey,
    endDayKey:
      endDayKey < startDayKey || endDayKey > lastDayKey ? lastDayKey : endDayKey,
  });

  return NextResponse.json({
    events,
    count: events.length,
  });
}
