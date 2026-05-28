import type { EventCategory, EventRow } from "@/lib/supabase-rows";

export type SubmissionStatus = "pending" | "approved" | "rejected";

/**
 * Pending row from `submissions` (admin moderation queue).
 * Columns mirror `supabase/migrations/*_init_schema.sql` — add
 * `schemas/submissions.*.json` + `npm run generate:rows` when pipeline needs it.
 */
export interface SubmissionRow {
  id: string;
  title: string;
  description: string;
  starts_at: string;
  ends_at: string | null;
  location: string;
  host: string;
  host_handle: string | null;
  category: EventCategory;
  tags: string[];
  source_url: string | null;
  image_url: string | null;
  is_free: boolean;
  rsvp_required: boolean;
  rsvp_url: string | null;
  submitter_name: string;
  submitter_email: string;
  submitter_org: string | null;
  status: SubmissionStatus;
  created_at: string;
}

/** Live event row for admin (generated EventRow + DB moderation columns). */
export type AdminEventRow = EventRow & {
  is_locked: boolean;
  created_at: string;
  updated_at: string;
};

/** Writable event fields for admin edit (server allowlist). */
export const ADMIN_EVENT_UPDATE_KEYS = [
  "title",
  "description",
  "starts_at",
  "ends_at",
  "location",
  "host",
  "host_handle",
  "category",
  "image_url",
  "rsvp_url",
  "is_free",
  "rsvp_required",
] as const;

export type AdminEventUpdatePayload = {
  title: string;
  description: string;
  starts_at: string;
  ends_at: string | null;
  location: string;
  host: string;
  host_handle: string | null;
  category: EventCategory;
  image_url: string | null;
  rsvp_url: string | null;
  is_free: boolean;
  rsvp_required: boolean;
};

/** Same ordering as `getEventsPage` on the public /events feed. */
export function sortEventsByFeedOrder(events: AdminEventRow[]): AdminEventRow[] {
  return [...events].sort((a, b) => {
    const byStart = a.starts_at.localeCompare(b.starts_at);
    if (byStart !== 0) return byStart;
    return a.id.localeCompare(b.id);
  });
}

export function matchesAdminSearch(
  query: string,
  ...fields: (string | null | undefined)[]
): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return fields.some((f) => f?.toLowerCase().includes(q));
}
