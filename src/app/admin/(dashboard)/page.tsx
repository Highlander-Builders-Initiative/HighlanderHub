import React from "react";
import { getAdminSupabase } from "@/lib/admin";
import { activeEventFilter } from "@/lib/events";
import AdminDashboardClient from "./AdminDashboardClient";

// Opt out of Next.js static rendering/caching for this route
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function AdminDashboardPage() {
  const supabase = getAdminSupabase();
  const nowIso = new Date().toISOString();

  const { data: events, error: eventErr } = await supabase
    .from("events")
    .select("*")
    .or(activeEventFilter(nowIso))
    // Match public /events feed: soonest first, id tie-breaker for stable pages.
    .order("starts_at", { ascending: true })
    .order("id", { ascending: true });

  if (eventErr) {
    console.error("Error fetching events for admin deck:", eventErr);
  }

  return <AdminDashboardClient initialEvents={events || []} />;
}
