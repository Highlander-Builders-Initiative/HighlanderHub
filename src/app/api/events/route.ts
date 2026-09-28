import { NextResponse } from "next/server";
import { EVENTS_PAGE_SIZE, getEventsPage } from "@/lib/events";
import { readEventFeedQuery } from "@/components/events/events-filters";

export const dynamic = "force-dynamic";

function readPositiveInt(value: string | null, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

const TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const sortAt = searchParams.get("after");
  const id = searchParams.get("afterId");
  // Cursors come from this route's own responses. Starting over on one it
  // cannot read would return page one with an equally unreadable cursor, and
  // the feed would request page one forever instead of showing an error.
  if ((sortAt || id) && !(sortAt && id && TIMESTAMP.test(sortAt))) {
    return NextResponse.json({ error: "Invalid cursor." }, { status: 400 });
  }
  const limit = readPositiveInt(searchParams.get("limit"), EVENTS_PAGE_SIZE);
  const page = await getEventsPage({
    after: sortAt && id ? { sortAt, id } : null,
    limit,
    ...readEventFeedQuery((key) => searchParams.get(key)),
  });

  return NextResponse.json({
    events: page.events,
    count: page.events.length,
    hasMore: page.hasMore,
    cursor: page.cursor,
  });
}
