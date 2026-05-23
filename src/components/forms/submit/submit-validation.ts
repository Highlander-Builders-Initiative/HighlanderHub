import { normalizeHttpUrl } from "@/lib/events/validation";
import type { EventCategory } from "@/types/event";

export type FieldName =
  | "title"
  | "starts_at"
  | "ends_at"
  | "location"
  | "host"
  | "source_url"
  | "image_url"
  | "rsvp_url"
  | "submitter_name"
  | "submitter_email";

export type FieldErrors = Partial<Record<FieldName, string>>;

const REQUIRED_FIELDS: FieldName[] = [
  "title",
  "starts_at",
  "location",
  "host",
  "submitter_name",
  "submitter_email",
];

const OPTIONAL_URL_FIELDS: FieldName[] = ["source_url", "image_url", "rsvp_url"];

const URL_ERROR = "Use an http(s) URL.";

export function validateSubmissionFields(form: FormData): FieldErrors {
  const errors = REQUIRED_FIELDS.reduce<FieldErrors>((next, field) => {
    if (!String(form.get(field) ?? "").trim()) {
      next[field] = "This field is required.";
    }
    return next;
  }, {});

  const rsvpRequired = form.get("rsvp_required") === "on";
  if (rsvpRequired && !String(form.get("rsvp_url") ?? "").trim()) {
    errors.rsvp_url = "This field is required.";
  }

  for (const field of OPTIONAL_URL_FIELDS) {
    const value = String(form.get(field) ?? "").trim();
    if (value && !normalizeHttpUrl(value)) {
      errors[field] = URL_ERROR;
    }
  }

  return errors;
}

export function buildSubmissionRow(
  form: FormData,
  startsAt: string,
  endsAt: string | null,
  imageUrl: string | null
) {
  const tagsRaw = String(form.get("tags") ?? "");

  return {
    title: String(form.get("title") ?? ""),
    description: String(form.get("description") ?? ""),
    starts_at: startsAt,
    ends_at: endsAt,
    location: String(form.get("location") ?? ""),
    host: String(form.get("host") ?? ""),
    category: form.get("category") as EventCategory,
    tags: tagsRaw
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean),
    source_url: normalizeHttpUrl(form.get("source_url")),
    image_url: imageUrl ?? normalizeHttpUrl(form.get("image_url")),
    is_free: form.get("is_free") === "on",
    rsvp_required: form.get("rsvp_required") === "on",
    rsvp_url: normalizeHttpUrl(form.get("rsvp_url")),
    submitter_name: String(form.get("submitter_name") ?? ""),
    submitter_email: String(form.get("submitter_email") ?? ""),
    submitter_org: String(form.get("submitter_org") ?? "") || null,
  };
}
