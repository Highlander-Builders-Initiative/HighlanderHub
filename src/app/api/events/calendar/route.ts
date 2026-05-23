import { NextResponse } from "next/server";
import { getCalendarEvents } from "@/lib/events";
import {
  addPacificDays,
  pacificCalendarGridRange,
  pacificTodayKey,
  startOfPacificMonthKey,
} from "@/lib/dates";

export const dynamic = "force-dynamic";

function readDayKey(value: string | null, fallback: string): string {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : fallback;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const defaultRange = pacificCalendarGridRange(
    startOfPacificMonthKey(pacificTodayKey())
  );
  const startDayKey = readDayKey(searchParams.get("start"), defaultRange.start);
  const endDayKey = readDayKey(searchParams.get("end"), defaultRange.end);

  const events = await getCalendarEvents({
    startDayKey,
    endDayKey:
      endDayKey < startDayKey ? addPacificDays(startDayKey, 41) : endDayKey,
  });

  return NextResponse.json({
    events,
    count: events.length,
  });
}
