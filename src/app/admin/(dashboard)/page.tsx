import React from "react";
import { getAdminSupabase } from "@/lib/admin";
import AdminDashboardClient from "./AdminDashboardClient";

// Opt out of Next.js static rendering/caching for this route
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function AdminDashboardPage() {
  const supabase = getAdminSupabase();

  // 1. Fetch pending manual submissions
  const { data: submissions, error: subErr } = await supabase
    .from("submissions")
    .select("*")
    .eq("status", "pending")
    .order("created_at", { ascending: false });

  if (subErr) {
    console.error("Error fetching submissions for admin deck:", subErr);
  }

  // 2. Fetch live events.
  // We fetch events starting from 7 days ago onwards to keep the dashboard
  // fast, responsive, and relevant. Older events don't require active editing.
  const sevenDaysAgo = new Date(
    Date.now() - 7 * 24 * 60 * 60 * 1000
  ).toISOString();

  const { data: events, error: eventErr } = await supabase
    .from("events")
    .select("*")
    .gte("starts_at", sevenDaysAgo)
    .order("starts_at", { ascending: false });

  if (eventErr) {
    console.error("Error fetching events for admin deck:", eventErr);
  }

  return (
    <AdminDashboardClient
      initialSubmissions={submissions || []}
      initialEvents={events || []}
    />
  );
}
