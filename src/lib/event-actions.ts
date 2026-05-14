import type { CampusEvent } from "@/types/event";
import { formatTimeRange } from "@/lib/dates";

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

export function shareHref(event: CampusEvent) {
  const url = event.rsvpUrl ?? event.sourceUrl;
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
