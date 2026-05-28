// Columns the public submit form is allowed to set. Everything else
// (status, reviewed_at, review_notes, id, created_at) is owned by the server
// or DB defaults, so we drop it from the insert to prevent mass-assignment.
const SUBMISSION_INSERT_FIELDS = [
  "title",
  "description",
  "starts_at",
  "ends_at",
  "location",
  "host",
  "category",
  "tags",
  "source_url",
  "image_url",
  "is_free",
  "rsvp_required",
  "rsvp_url",
  "submitter_name",
  "submitter_email",
  "submitter_org",
] as const;

export function pickSubmissionFields(
  body: Record<string, unknown>
): Record<string, unknown> {
  const row: Record<string, unknown> = {};
  for (const field of SUBMISSION_INSERT_FIELDS) {
    if (field in body) {
      row[field] = body[field];
    }
  }
  return row;
}
