import { NextResponse } from "next/server";
import { getEvents } from "@/lib/events";

export async function GET() {
  const events = await getEvents();
  return NextResponse.json({ events, count: events.length });
}
