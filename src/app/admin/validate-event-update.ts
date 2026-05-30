import { EVENT_CATEGORIES, EVENT_CONTENT_KINDS } from "@/lib/supabase-rows";
import {
  ADMIN_EVENT_UPDATE_KEYS,
  type AdminEventUpdatePayload,
} from "./types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isOptionalStringOrNull(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isIsoTimestamp(value: unknown): value is string {
  if (typeof value !== "string" || !value.trim()) return false;
  const ms = Date.parse(value);
  return !Number.isNaN(ms);
}

/**
 * Validates client update payload against the admin allowlist.
 * Rejects unknown keys and non-writable columns (id, source, is_locked, etc.).
 */
export function parseAdminEventUpdate(
  raw: unknown
): { ok: true; payload: AdminEventUpdatePayload } | { ok: false; error: string } {
  if (!isRecord(raw)) {
    return { ok: false, error: "Invalid update payload." };
  }

  const unknownKeys = Object.keys(raw).filter(
    (k) => !(ADMIN_EVENT_UPDATE_KEYS as readonly string[]).includes(k)
  );
  if (unknownKeys.length > 0) {
    return {
      ok: false,
      error: `Disallowed fields: ${unknownKeys.join(", ")}`,
    };
  }

  for (const key of ADMIN_EVENT_UPDATE_KEYS) {
    if (!(key in raw)) {
      return { ok: false, error: `Missing required field: ${key}` };
    }
  }

  const title = raw.title;
  const description = raw.description;
  const starts_at = raw.starts_at;
  const ends_at = raw.ends_at;
  const location = raw.location;
  const host = raw.host;
  const host_handle = raw.host_handle;
  const category = raw.category;
  const content_kind = raw.content_kind;
  const image_url = raw.image_url;
  const rsvp_url = raw.rsvp_url;
  const is_free = raw.is_free;
  const rsvp_required = raw.rsvp_required;

  if (!isNonEmptyString(title)) {
    return { ok: false, error: "title must be a non-empty string." };
  }
  if (typeof description !== "string") {
    return { ok: false, error: "description must be a string." };
  }
  if (!isIsoTimestamp(starts_at)) {
    return { ok: false, error: "starts_at must be a valid ISO timestamp." };
  }
  if (ends_at !== null && !isIsoTimestamp(ends_at)) {
    return { ok: false, error: "ends_at must be null or a valid ISO timestamp." };
  }
  if (!isNonEmptyString(location)) {
    return { ok: false, error: "location must be a non-empty string." };
  }
  if (!isNonEmptyString(host)) {
    return { ok: false, error: "host must be a non-empty string." };
  }
  if (!isOptionalStringOrNull(host_handle)) {
    return { ok: false, error: "host_handle must be a string or null." };
  }
  if (
    typeof category !== "string" ||
    !(EVENT_CATEGORIES as readonly string[]).includes(category)
  ) {
    return { ok: false, error: "category is invalid." };
  }
  if (
    typeof content_kind !== "string" ||
    !(EVENT_CONTENT_KINDS as readonly string[]).includes(content_kind)
  ) {
    return { ok: false, error: "content_kind is invalid." };
  }
  if (!isOptionalStringOrNull(image_url)) {
    return { ok: false, error: "image_url must be a string or null." };
  }
  if (!isOptionalStringOrNull(rsvp_url)) {
    return { ok: false, error: "rsvp_url must be a string or null." };
  }
  if (typeof is_free !== "boolean") {
    return { ok: false, error: "is_free must be a boolean." };
  }
  if (typeof rsvp_required !== "boolean") {
    return { ok: false, error: "rsvp_required must be a boolean." };
  }

  return {
    ok: true,
    payload: {
      title: title.trim(),
      description,
      starts_at,
      ends_at: ends_at as string | null,
      location: location.trim(),
      host: host.trim(),
      host_handle: host_handle === "" ? null : host_handle,
      category: category as AdminEventUpdatePayload["category"],
      content_kind: content_kind as AdminEventUpdatePayload["content_kind"],
      image_url: image_url === "" ? null : image_url,
      rsvp_url: rsvp_url === "" ? null : rsvp_url,
      is_free,
      rsvp_required,
    },
  };
}
