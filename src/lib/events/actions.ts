import type { CampusEvent } from "@/types/event";
import { formatTimeRange } from "@/lib/dates";
import { normalizeHttpUrl } from "@/lib/events/validation";

function calendarDate(value: string) {
  return new Date(value)
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\.\d{3}Z$/, "Z");
}

function addHours(value: string, hours: number) {
  return new Date(
    new Date(value).getTime() + hours * 60 * 60 * 1000
  ).toISOString();
}

export function calendarHref(event: CampusEvent) {
  const end = event.endsAt ?? addHours(event.startsAt, 1);
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: event.title,
    dates: `${calendarDate(event.startsAt)}/${calendarDate(end)}`,
    details: event.description,
    location: event.location,
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

/** Path to the per-event `.ics` download served by the route handler. */
export function icsHref(eventId: string) {
  return `/events/${encodeURIComponent(eventId)}/event.ics`;
}

/** Escape a TEXT value per RFC 5545 (backslash, semicolon, comma, newlines). */
function escapeIcsText(value: string) {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,")
    .replace(/\r?\n/g, "\\n");
}

const textEncoder = new TextEncoder();

/** Fold a content line to <=75 octets with CRLF + space continuations. */
function foldIcsLine(line: string) {
  if (textEncoder.encode(line).length <= 75) return line;
  const chunks: string[] = [];
  let current = "";

  for (const char of line) {
    const next = current + char;
    if (current && textEncoder.encode(next).length > 75) {
      chunks.push(current);
      current = ` ${char}`;
    } else {
      current = next;
    }
  }
  if (current) chunks.push(current);
  return chunks.join("\r\n");
}

/**
 * A single-event VCALENDAR. Universal: Apple Calendar opens it natively on
 * iOS, Outlook imports it, and Google Calendar accepts it via import — so it
 * complements `calendarHref` (Google's web template) for the rest of campus.
 */
export function buildIcsContent(event: CampusEvent, now = new Date()) {
  const end = event.endsAt ?? addHours(event.startsAt, 1);
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Highlander Hub//Events//EN",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    `UID:${event.id}@highlanderhub.app`,
    `DTSTAMP:${calendarDate(now.toISOString())}`,
    `DTSTART:${calendarDate(event.startsAt)}`,
    `DTEND:${calendarDate(end)}`,
    `SUMMARY:${escapeIcsText(event.title)}`,
    `DESCRIPTION:${escapeIcsText(event.description)}`,
    `LOCATION:${escapeIcsText(event.location)}`,
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return `${lines.map(foldIcsLine).join("\r\n")}\r\n`;
}

export function shareHref(event: CampusEvent) {
  const url = normalizeHttpUrl(event.rsvpUrl) ?? normalizeHttpUrl(event.sourceUrl);
  const body = [
    event.title,
    formatTimeRange(event.startsAt, event.endsAt),
    event.location,
    url,
  ]
    .filter(Boolean)
    .join("\n");
  return `mailto:?subject=${encodeURIComponent(
    event.title
  )}&body=${encodeURIComponent(body)}`;
}
