import { normalizeHttpUrl } from "@/lib/events/validation";
import {
  EVENT_CATEGORIES,
  type EventCategory,
  type EventContentKind,
} from "@/lib/supabase-rows";
import {
  coerceSubmittableContentKind,
  isSubmittableContentKind,
} from "@/lib/events/content-kind";

export type SubmissionInsertRow = {
  title: string;
  description: string;
  starts_at: string;
  ends_at: string | null;
  location: string;
  host: string;
  category: EventCategory;
  content_kind: EventContentKind;
  tags: string[];
  source_url: string | null;
  image_url: string | null;
  is_free: boolean;
  has_free_food: boolean;
  rsvp_required: boolean;
  rsvp_url: string | null;
  submitter_name: string;
  submitter_email: string;
  submitter_org: string | null;
};

export type SubmissionParseResult =
  | { ok: true; row: SubmissionInsertRow }
  | { ok: false; error: string };

// Columns the public submit form is allowed to set. Everything else
// (status, reviewed_at, review_notes, id, created_at) is owned by the server
// or DB defaults, so we reject it before insert to prevent mass-assignment.
const SUBMISSION_INSERT_FIELDS = [
  "title",
  "description",
  "starts_at",
  "ends_at",
  "location",
  "host",
  "category",
  "content_kind",
  "tags",
  "source_url",
  "image_url",
  "is_free",
  "has_free_food",
  "rsvp_required",
  "rsvp_url",
  "submitter_name",
  "submitter_email",
  "submitter_org",
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function trimmedString(value: unknown): string | null {
  return typeof value === "string" ? value.trim() : null;
}

function parseIsoTimestamp(value: unknown): string | null {
  const text = trimmedString(value);
  if (!text) return null;
  const ms = Date.parse(text);
  return Number.isNaN(ms) ? null : new Date(ms).toISOString();
}

function parseOptionalString(
  value: unknown,
  field: string
): { ok: true; value: string | null } | { ok: false; error: string } {
  if (value === null) return { ok: true, value: null };
  if (typeof value !== "string") {
    return { ok: false, error: `${field} must be a string or null.` };
  }
  const text = value.trim();
  return { ok: true, value: text || null };
}

function parseOptionalUrl(
  value: unknown,
  field: string
): { ok: true; value: string | null } | { ok: false; error: string } {
  const optional = parseOptionalString(value, field);
  if (!optional.ok || !optional.value) return optional;

  const url = normalizeHttpUrl(optional.value);
  if (!url) {
    return { ok: false, error: `${field} must be an http(s) URL.` };
  }
  return { ok: true, value: url };
}

function parseTags(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null;
  if (!value.every((tag) => typeof tag === "string")) return null;
  return value.map((tag) => tag.trim()).filter(Boolean);
}

function isSubmissionEmail(value: string): boolean {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value);
}

export function buildSubmissionRow(
  form: FormData,
  startsAt: string,
  endsAt: string | null,
  imageUrl: string | null
): SubmissionInsertRow {
  const tagsRaw = String(form.get("tags") ?? "");

  return {
    title: String(form.get("title") ?? ""),
    description: String(form.get("description") ?? ""),
    starts_at: startsAt,
    ends_at: endsAt,
    location: String(form.get("location") ?? ""),
    host: String(form.get("host") ?? ""),
    category: form.get("category") as EventCategory,
    content_kind: coerceSubmittableContentKind(form.get("content_kind")),
    tags: tagsRaw
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean),
    source_url: normalizeHttpUrl(form.get("source_url")),
    image_url: imageUrl ?? normalizeHttpUrl(form.get("image_url")),
    is_free: form.get("is_free") === "on",
    has_free_food: form.get("has_free_food") === "on",
    rsvp_required: form.get("rsvp_required") === "on",
    rsvp_url: normalizeHttpUrl(form.get("rsvp_url")),
    submitter_name: String(form.get("submitter_name") ?? ""),
    submitter_email: String(form.get("submitter_email") ?? ""),
    submitter_org: String(form.get("submitter_org") ?? "") || null,
  };
}

export function parseSubmissionInsert(raw: unknown): SubmissionParseResult {
  if (!isRecord(raw)) {
    return { ok: false, error: "Invalid submission payload." };
  }

  const unknownKeys = Object.keys(raw).filter(
    (key) => !(SUBMISSION_INSERT_FIELDS as readonly string[]).includes(key)
  );
  if (unknownKeys.length > 0) {
    return {
      ok: false,
      error: `Disallowed fields: ${unknownKeys.join(", ")}`,
    };
  }

  const title = trimmedString(raw.title);
  if (!title || title.length < 3 || title.length > 200) {
    return { ok: false, error: "title must be 3 to 200 characters." };
  }

  if (typeof raw.description !== "string") {
    return { ok: false, error: "description must be a string." };
  }

  const startsAt = parseIsoTimestamp(raw.starts_at);
  if (!startsAt) {
    return { ok: false, error: "starts_at must be a valid timestamp." };
  }

  let endsAt: string | null = null;
  if (raw.ends_at !== null) {
    endsAt = parseIsoTimestamp(raw.ends_at);
    if (!endsAt) {
      return { ok: false, error: "ends_at must be null or a valid timestamp." };
    }
    if (new Date(endsAt).getTime() < new Date(startsAt).getTime()) {
      return { ok: false, error: "ends_at must be at or after starts_at." };
    }
  }

  const location = trimmedString(raw.location);
  if (!location) {
    return { ok: false, error: "location must be a non-empty string." };
  }

  const host = trimmedString(raw.host);
  if (!host) {
    return { ok: false, error: "host must be a non-empty string." };
  }

  const category = raw.category;
  if (
    typeof category !== "string" ||
    !(EVENT_CATEGORIES as readonly string[]).includes(category)
  ) {
    return { ok: false, error: "category is invalid." };
  }

  if (!isSubmittableContentKind(raw.content_kind)) {
    return {
      ok: false,
      error: "content_kind must be student_event or student_deadline.",
    };
  }

  const tags = parseTags(raw.tags);
  if (!tags) {
    return { ok: false, error: "tags must be an array of strings." };
  }

  const sourceUrl = parseOptionalUrl(raw.source_url, "source_url");
  if (!sourceUrl.ok) return sourceUrl;

  const imageUrl = parseOptionalUrl(raw.image_url, "image_url");
  if (!imageUrl.ok) return imageUrl;

  if (typeof raw.is_free !== "boolean") {
    return { ok: false, error: "is_free must be a boolean." };
  }

  if (typeof raw.has_free_food !== "boolean") {
    return { ok: false, error: "has_free_food must be a boolean." };
  }

  if (typeof raw.rsvp_required !== "boolean") {
    return { ok: false, error: "rsvp_required must be a boolean." };
  }

  const rsvpUrl = parseOptionalUrl(raw.rsvp_url, "rsvp_url");
  if (!rsvpUrl.ok) return rsvpUrl;
  if (raw.rsvp_required && !rsvpUrl.value) {
    return {
      ok: false,
      error: "rsvp_url is required when rsvp_required is true.",
    };
  }

  const submitterName = trimmedString(raw.submitter_name);
  if (!submitterName || submitterName.length > 100) {
    return { ok: false, error: "submitter_name must be 1 to 100 characters." };
  }

  const submitterEmail = trimmedString(raw.submitter_email);
  if (!submitterEmail || !isSubmissionEmail(submitterEmail)) {
    return { ok: false, error: "submitter_email is invalid." };
  }

  const submitterOrg = parseOptionalString(raw.submitter_org, "submitter_org");
  if (!submitterOrg.ok) return submitterOrg;

  return {
    ok: true,
    row: {
      title,
      description: raw.description,
      starts_at: startsAt,
      ends_at: endsAt,
      location,
      host,
      category: category as EventCategory,
      content_kind: raw.content_kind,
      tags,
      source_url: sourceUrl.value,
      image_url: imageUrl.value,
      is_free: raw.is_free,
      has_free_food: raw.has_free_food,
      rsvp_required: raw.rsvp_required,
      rsvp_url: rsvpUrl.value,
      submitter_name: submitterName,
      submitter_email: submitterEmail,
      submitter_org: submitterOrg.value,
    },
  };
}
