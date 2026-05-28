import { normalizeHttpUrl } from "@/lib/events/validation";

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
