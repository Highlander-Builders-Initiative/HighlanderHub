import { parsePacificDateTimeInput } from "@/lib/dates";

type TimeField = "starts_at" | "ends_at";

export type EventTimeValidation = {
  startsAt: string | null;
  endsAt: string | null;
  field: TimeField | null;
  error: string | null;
};

function asTrimmedString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function normalizeHttpUrl(value: unknown): string | null {
  const text = asTrimmedString(value);
  if (!text) return null;

  try {
    const url = new URL(text);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    return url.toString();
  } catch {
    return null;
  }
}

export function validateEventTimes(
  startValue: unknown,
  endValue: unknown
): EventTimeValidation {
  const startsAt = parsePacificDateTimeInput(startValue);
  if (!startsAt) {
    return {
      startsAt: null,
      endsAt: null,
      field: "starts_at",
      error: "Start time is invalid.",
    };
  }

  const rawEnd = asTrimmedString(endValue);
  if (!rawEnd) {
    return { startsAt, endsAt: null, field: null, error: null };
  }

  const endsAt = parsePacificDateTimeInput(rawEnd);
  if (!endsAt) {
    return {
      startsAt,
      endsAt: null,
      field: "ends_at",
      error: "End time is invalid.",
    };
  }

  if (new Date(endsAt).getTime() < new Date(startsAt).getTime()) {
    return {
      startsAt,
      endsAt,
      field: "ends_at",
      error: "End time must be at or after the start time.",
    };
  }

  return { startsAt, endsAt, field: null, error: null };
}
