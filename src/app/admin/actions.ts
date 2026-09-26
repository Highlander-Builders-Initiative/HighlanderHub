"use server";

import { cookies, headers } from "next/headers";
import { revalidatePath, revalidateTag } from "next/cache";
import { EVENTS_CACHE_TAG } from "@/lib/events";
import { signSession, verifySession, getAdminSupabase, getAdminPassword, verifyPassword } from "@/lib/admin";
import { ADMIN_LOGIN_RATE_LIMIT, clientIp, rateLimit } from "@/lib/rate-limit";
import { parseAdminEventUpdate } from "./validate-event-update";
import { duplicateMergeChanges } from "./duplicate-merge";
import type { AdminEventRow, AdminEventUpdatePayload } from "./types";

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

function isEventId(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= 200;
}

/** Both listings of a reviewed pair, as they are now. */
async function loadDuplicatePair(firstId: unknown, secondId: unknown) {
  if (!isEventId(firstId) || !isEventId(secondId) || firstId === secondId) {
    return { ok: false as const, error: "Choose two different events." };
  }
  const { data, error } = await getAdminSupabase()
    .from("events")
    .select("*")
    .in("id", [firstId, secondId])
    .overrideTypes<AdminEventRow[], { merge: false }>();
  if (error) {
    return { ok: false as const, error: `Failed to load events: ${error.message}` };
  }
  const first = data?.find((row) => row.id === firstId);
  const second = data?.find((row) => row.id === secondId);
  if (!first || !second) {
    return {
      ok: false as const,
      error: "One of these listings is already gone. Refresh to see the current queue.",
    };
  }
  return { ok: true as const, first, second };
}

function revalidateEvents() {
  revalidateTag(EVENTS_CACHE_TAG, "max");
  revalidatePath("/events");
  revalidatePath("/admin");
}

/**
 * Keeps one listing of a duplicate pair and removes the other. The kept
 * listing takes whatever details it lacks, the removed listing's sources are
 * pointed at it so a later scrape does not recreate the duplicate, and the
 * decision is saved for the pipeline. `seen` holds each listing's updated_at
 * as the admin reviewed it; a listing changed since then aborts the merge.
 */
export async function mergeDuplicateEvents(
  keptId: string,
  removedId: string,
  seen: { kept: string; removed: string }
) {
  await requireAdmin();

  const pair = await loadDuplicatePair(keptId, removedId);
  if (!pair.ok) return { success: false, error: pair.error };
  const { first: kept, second: removed } = pair;
  if (kept.updated_at !== seen?.kept || removed.updated_at !== seen?.removed) {
    return {
      success: false,
      error: "One of these listings changed since this page loaded. Refresh and review it again.",
    };
  }

  const { changes } = duplicateMergeChanges(kept, removed);
  const { error } = await getAdminSupabase().rpc("merge_duplicate_events", {
    kept_id: kept.id,
    removed_id: removed.id,
    changes,
    kept_updated_at: kept.updated_at,
    removed_updated_at: removed.updated_at,
  });
  if (error) {
    return { success: false, error: `Failed to merge events: ${error.message}` };
  }

  revalidateEvents();
  return { success: true };
}

/**
 * Records that a flagged pair are different events. Both listings stay, and
 * reconciliation will neither merge them nor flag them again.
 */
export async function markEventsDifferent(firstId: string, secondId: string) {
  await requireAdmin();

  const pair = await loadDuplicatePair(firstId, secondId);
  if (!pair.ok) return { success: false, error: pair.error };
  // The queue orders each pair by code point, as the pipeline does.
  const [a, b] =
    pair.first.id < pair.second.id ? [pair.first, pair.second] : [pair.second, pair.first];

  const { error } = await getAdminSupabase()
    .from("event_duplicate_reviews")
    .upsert(
      {
        event_id: a.id,
        other_event_id: b.id,
        status: "different",
        kept_event_id: null,
        event_snapshot: a,
        other_snapshot: b,
        decided_at: new Date().toISOString(),
      },
      { onConflict: "event_id,other_event_id" }
    );
  if (error) {
    return { success: false, error: `Failed to save the decision: ${error.message}` };
  }

  revalidatePath("/admin");
  return { success: true };
}
