import { NextResponse } from "next/server";
import { EVENTS_PAGE_SIZE, getEventsPage } from "@/lib/events";

export const dynamic = "force-dynamic";

function readPositiveInt(value: string | null, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const offset = readPositiveInt(searchParams.get("offset"), 0);
  const limit = readPositiveInt(searchParams.get("limit"), EVENTS_PAGE_SIZE);
  const page = await getEventsPage({ offset, limit });

  return NextResponse.json({
    events: page.events,
    count: page.events.length,
    hasMore: page.hasMore,
    nextOffset: page.nextOffset,
  });
}
