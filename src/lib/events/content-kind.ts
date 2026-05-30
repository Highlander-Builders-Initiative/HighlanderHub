import {
  EVENT_CONTENT_KINDS,
  type EventContentKind,
} from "@/lib/supabase-rows";

export { EVENT_CONTENT_KINDS };
export type { EventContentKind };

/**
 * Kinds the public `/events` surfaces may show. Mirrors the DB-level filter
 * applied in `src/lib/events/index.ts`; `fundraiser` and `other` are never
 * public. This is the visibility predicate the plan asks app helpers to
 * mirror — classification itself lives in the pipeline.
 */
export const PUBLIC_CONTENT_KINDS: EventContentKind[] = [
  "student_event",
  "student_deadline",
];

/** Kinds the public submit form is allowed to set (no fundraiser/other). */
export const SUBMITTABLE_CONTENT_KINDS: EventContentKind[] = [
  "student_event",
  "student_deadline",
];

export const EVENT_CONTENT_KIND_LABELS: Record<EventContentKind, string> = {
  student_event: "Event",
  student_deadline: "Deadline",
  fundraiser: "Fundraiser",
  other: "Other",
};

export function isContentKind(value: unknown): value is EventContentKind {
  return (
    typeof value === "string" &&
    (EVENT_CONTENT_KINDS as readonly string[]).includes(value)
  );
}

export function isPublicContentKind(value: unknown): value is EventContentKind {
  return (
    isContentKind(value) && PUBLIC_CONTENT_KINDS.includes(value)
  );
}

export function isSubmittableContentKind(
  value: unknown
): value is EventContentKind {
  return (
    isContentKind(value) && SUBMITTABLE_CONTENT_KINDS.includes(value)
  );
}

/** Coerce an untrusted value to a known kind, falling back to `fallback`. */
export function coerceContentKind(
  value: unknown,
  fallback: EventContentKind = "student_event"
): EventContentKind {
  return isContentKind(value) ? value : fallback;
}

/** Coerce to a submittable kind; non-submittable/unknown values become Event. */
export function coerceSubmittableContentKind(
  value: unknown
): EventContentKind {
  return isSubmittableContentKind(value) ? value : "student_event";
}

export function isDeadlineKind(value: unknown): boolean {
  return value === "student_deadline";
}
