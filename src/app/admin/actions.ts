"use server";

import { cookies } from "next/headers";
import { revalidatePath, revalidateTag } from "next/cache";
import { EVENTS_CACHE_TAG } from "@/lib/events";
import { signSession, verifySession, getAdminSupabase, getAdminPassword, verifyPassword } from "@/lib/admin";
import { parseAdminEventUpdate } from "./validate-event-update";
import type { AdminEventUpdatePayload } from "./types";

/**
 * Verifies if the current requester is authorized as an admin.
 * Throws an error if not authenticated.
 */
function requireAdmin() {
  const session = cookies().get("hh_admin_session")?.value;
  if (!verifySession(session)) {
    throw new Error("Unauthorized. Please log in as an administrator.");
  }
}

/**
 * Authenticates the admin using the secure environment password.
 * Sets an HTTP-only cookie containing the cryptographically signed session.
 */
export async function loginAdmin(password: string) {
  if (!getAdminPassword()) {
    return {
      success: false,
      error: "Admin login is not configured. Set ADMIN_PASSWORD in the environment.",
    };
  }

  if (!verifyPassword(password)) {
    return { success: false, error: "Incorrect administrator password." };
  }

  const durationMs = 7 * 24 * 60 * 60 * 1000; // 7 Days
  const expiresAt = Date.now() + durationMs;
  const sessionToken = signSession(expiresAt);

  cookies().set("hh_admin_session", sessionToken, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    expires: new Date(expiresAt),
  });

  return { success: true };
}

/**
 * Log out and clear the admin session cookie.
 */
export async function logoutAdmin() {
  cookies().set("hh_admin_session", "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 0,
  });

  return { success: true };
}

/**
 * Approves a public submission.
 * Copies the submission data into the canonical `events` table,
 * sets its status to 'approved', and records the review timestamp.
 */
export async function approveSubmission(submissionId: string) {
  requireAdmin();

  const supabase = getAdminSupabase();

  // 1. Fetch the pending submission
  const { data: submission, error: fetchErr } = await supabase
    .from("submissions")
    .select("*")
    .eq("id", submissionId)
    .single();

  if (fetchErr || !submission) {
    return {
      success: false,
      error: `Submission not found: ${fetchErr?.message || "Unknown error"}`,
    };
  }

  // 2. Map submission fields into events table format
  const eventId = `manual_${submission.id}`;
  const eventRow = {
    id: eventId,
    title: submission.title,
    description: submission.description,
    starts_at: submission.starts_at,
    ends_at: submission.ends_at,
    location: submission.location,
    host: submission.host,
    host_handle: submission.host_handle || null,
    category: submission.category,
    tags: submission.tags || [],
    source: "manual",
    source_url: submission.source_url || null,
    image_url: submission.image_url || null,
    is_free: submission.is_free,
    rsvp_required: submission.rsvp_required,
    rsvp_url: submission.rsvp_url || null,
    is_locked: true, // Manual events are locked by default to prevent any scraping collision
  };

  // 3. Upsert into events
  const { error: eventErr } = await supabase
    .from("events")
    .upsert(eventRow);

  if (eventErr) {
    return {
      success: false,
      error: `Failed to create event: ${eventErr.message}`,
    };
  }

  // 4. Update submission status to 'approved'
  const { error: subErr } = await supabase
    .from("submissions")
    .update({
      status: "approved",
      reviewed_at: new Date().toISOString(),
    })
    .eq("id", submissionId);

  if (subErr) {
    const { error: rollbackErr } = await supabase
      .from("events")
      .delete()
      .eq("id", eventId);

    const rollbackNote = rollbackErr
      ? ` Rollback delete also failed: ${rollbackErr.message}`
      : " The event was removed to avoid a half-approved state.";

    return {
      success: false,
      error: `Failed to update submission status: ${subErr.message}.${rollbackNote}`,
    };
  }

  // Revalidate both /events feed and admin dashboard path
  revalidateTag(EVENTS_CACHE_TAG);
  revalidatePath("/events");
  revalidatePath("/admin");

  return { success: true };
}

/**
 * Rejects a public submission.
 * Marks status as 'rejected' and stores optional notes.
 */
export async function rejectSubmission(submissionId: string, notes?: string) {
  requireAdmin();

  const supabase = getAdminSupabase();

  const { error } = await supabase
    .from("submissions")
    .update({
      status: "rejected",
      reviewed_at: new Date().toISOString(),
      review_notes: notes || "Rejected by moderator",
    })
    .eq("id", submissionId);

  if (error) {
    return { success: false, error: `Failed to reject: ${error.message}` };
  }

  revalidatePath("/admin");
  return { success: true };
}

/**
 * Updates a live event.
 * Crucially, set `is_locked = true` so that subsequent scraping runs
 * respect and do NOT overwrite these manual modifications.
 */
export async function updateEvent(eventId: string, updatedFields: unknown) {
  requireAdmin();

  const parsed = parseAdminEventUpdate(updatedFields);
  if (!parsed.ok) {
    return { success: false, error: parsed.error };
  }

  const supabase = getAdminSupabase();

  // Only allowlisted columns; is_locked always forced server-side.
  const payload: AdminEventUpdatePayload & {
    is_locked: true;
    updated_at: string;
  } = {
    ...parsed.payload,
    is_locked: true,
    updated_at: new Date().toISOString(),
  };

  const { error } = await supabase
    .from("events")
    .update(payload)
    .eq("id", eventId);

  if (error) {
    return { success: false, error: `Failed to update event: ${error.message}` };
  }

  revalidateTag(EVENTS_CACHE_TAG);
  revalidatePath("/events");
  revalidatePath("/admin");

  return { success: true };
}

/**
 * Deletes a live event from the bulletin.
 */
export async function deleteEvent(eventId: string) {
  requireAdmin();

  const supabase = getAdminSupabase();

  const { error: tombstoneError } = await supabase
    .from("deleted_events")
    .upsert({ event_id: eventId, deleted_at: new Date().toISOString() });

  if (tombstoneError) {
    return {
      success: false,
      error: `Failed to mark event as deleted: ${tombstoneError.message}`,
    };
  }

  const { error } = await supabase
    .from("events")
    .delete()
    .eq("id", eventId);

  if (error) {
    return { success: false, error: `Failed to delete event: ${error.message}` };
  }

  revalidateTag(EVENTS_CACHE_TAG);
  revalidatePath("/events");
  revalidatePath("/admin");

  return { success: true };
}
