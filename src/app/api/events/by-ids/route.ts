import { NextResponse } from "next/server";
import { getEventById } from "@/lib/events";
import type { CampusEvent } from "@/types/event";

export const dynamic = "force-dynamic";

// Caps the fan-out; comfortably above any realistic saved shortlist.
const MAX_IDS = 100;

// Resolves a comma-separated id list to events for the /saved view. Reuses the
// per-id Data Cache (getEventById), so this is cheap and adds no new query.
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const ids = (searchParams.get("ids") ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean)
    .slice(0, MAX_IDS);

  const resolved = await Promise.all(ids.map((id) => getEventById(id)));
  const events = resolved
    .filter((event): event is CampusEvent => event !== null)
    .sort((a, b) => a.startsAt.localeCompare(b.startsAt));

  return NextResponse.json({ events, count: events.length });
}
