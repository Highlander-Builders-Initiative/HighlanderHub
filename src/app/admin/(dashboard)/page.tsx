import React from "react";
import { getAdminSupabase } from "@/lib/admin";
import { activeEventFilter } from "@/lib/events";
import AdminDashboardClient from "./AdminDashboardClient";
import type { AdminEventRow, DuplicateReviewPair } from "../types";

// Opt out of Next.js static rendering/caching for this route
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function AdminDashboardPage() {
  const supabase = getAdminSupabase();
  const nowIso = new Date().toISOString();

  const [{ data: events, error: eventErr }, { data: queue, error: queueErr }] =
    await Promise.all([
      supabase
        .from("events")
        .select("*")
        .or(activeEventFilter(nowIso))
        // Match public /events feed: soonest first, id tie-breaker for stable pages.
        .order("starts_at", { ascending: true })
        .order("id", { ascending: true })
        .overrideTypes<AdminEventRow[], { merge: false }>(),
      supabase
        .from("event_duplicate_reviews")
        .select("event_id, other_event_id")
        .eq("status", "pending"),
    ]);

  if (eventErr) {
    console.error("Error fetching events for admin deck:", eventErr);
  }
  if (queueErr) {
    console.error("Error fetching duplicate review queue:", queueErr);
  }

  // The pipeline refreshes the queue each run; a pair whose listing has since
  // ended, merged or been deleted no longer needs a decision.
  const live = new Map((events ?? []).map((event) => [event.id, event]));
  const duplicatePairs: DuplicateReviewPair[] = (queue ?? [])
    .flatMap(({ event_id, other_event_id }) => {
      const first = live.get(event_id);
      const second = live.get(other_event_id);
      return first && second ? [{ first, second }] : [];
    })
    .sort((a, b) => a.first.starts_at.localeCompare(b.first.starts_at));

  return (
    <AdminDashboardClient
      initialEvents={events || []}
      duplicatePairs={duplicatePairs}
      duplicateQueueError={queueErr ? queueErr.message : null}
    />
  );
}
