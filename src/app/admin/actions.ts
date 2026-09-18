"use server";

import { cookies, headers } from "next/headers";
import { revalidatePath, revalidateTag } from "next/cache";
import { EVENTS_CACHE_TAG } from "@/lib/events";
import { signSession, verifySession, getAdminSupabase, getAdminPassword, verifyPassword } from "@/lib/admin";
import { ADMIN_LOGIN_RATE_LIMIT, clientIp, rateLimit } from "@/lib/rate-limit";
import { parseAdminEventUpdate } from "./validate-event-update";
import type { AdminEventUpdatePayload } from "./types";

/**
 * Verifies if the current requester is authorized as an admin.
 * Throws an error if not authenticated.
 */
async function requireAdmin() {
  const cookieStore = await cookies();
  const session = cookieStore.get("hh_admin_session")?.value;
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

  // Throttle attempts per IP so the single shared password can't be brute-forced.
  const limit = rateLimit(
    `admin-login:${clientIp(await headers())}`,
    ADMIN_LOGIN_RATE_LIMIT
  );
  if (!limit.ok) {
    const minutes = Math.ceil(limit.retryAfterSeconds / 60);
    return {
      success: false,
      error: `Too many attempts. Try again in about ${minutes} minute${
        minutes === 1 ? "" : "s"
      }.`,
    };
  }

  if (!verifyPassword(password)) {
    return { success: false, error: "Incorrect administrator password." };
  }

  const durationMs = 7 * 24 * 60 * 60 * 1000; // 7 Days
  const expiresAt = Date.now() + durationMs;
  const sessionToken = signSession(expiresAt);

  const cookieStore = await cookies();
  cookieStore.set("hh_admin_session", sessionToken, {
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
  const cookieStore = await cookies();
  cookieStore.set("hh_admin_session", "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 0,
  });

  return { success: true };
}

/**
 * Updates a live event.
 * Crucially, set `is_locked = true` so that subsequent scraping runs
 * respect and do NOT overwrite these manual modifications.
 */
export async function updateEvent(eventId: string, updatedFields: unknown) {
  await requireAdmin();

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

  revalidateTag(EVENTS_CACHE_TAG, "max");
  revalidatePath("/events");
  revalidatePath("/admin");

  return { success: true };
}

/**
 * Deletes a live event from the bulletin.
 */
export async function deleteEvent(eventId: string) {
  await requireAdmin();

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

  revalidateTag(EVENTS_CACHE_TAG, "max");
  revalidatePath("/events");
  revalidatePath("/admin");

  return { success: true };
}
