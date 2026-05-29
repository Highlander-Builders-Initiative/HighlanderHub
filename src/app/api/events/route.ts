import { NextResponse } from "next/server";
import { EVENTS_PAGE_SIZE, getEventsByIds, getEventsPage } from "@/lib/events";

export const dynamic = "force-dynamic";

function readPositiveInt(value: string | null, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);

  // Search backfill: resolve full records for a comma-separated id set. The
  // client only requests ids it knows match (from the full count source) but
  // hasn't paged into the feed yet.
  const idsParam = searchParams.get("ids");
  if (idsParam !== null) {
    const ids = idsParam.split(",").map((id) => id.trim()).filter(Boolean);
    const events = await getEventsByIds(ids);
    return NextResponse.json({ events, count: events.length });
  }

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
