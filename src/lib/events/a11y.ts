import type { CampusEvent } from "@/types/event";
import { EVENT_CATEGORY_LABELS } from "@/types/event";
import { isDeadlineKind } from "@/lib/events/content-kind";
import { formatAllDay, formatTime, relativeDay } from "@/lib/dates";

/** Link name for mosaic / marquee tiles (title + day, no time). */
export function eventTileLinkLabel(event: CampusEvent): string {
  return `${event.title}, ${relativeDay(event.startsAt)}`;
}

/** Image alt when the flyer sits inside a link that already has eventTileLinkLabel. */
export function eventFlyerAlt(event: CampusEvent): string {
  return `${eventTileLinkLabel(event)} flyer`;
}

/**
 * Link name for list / calendar rows. Leads with what the card's first tag
 * shows: Deadline, else the category.
 */
export function eventListLinkLabel(event: CampusEvent): string {
  const day = relativeDay(event.startsAt);
  if (isDeadlineKind(event.contentKind)) {
    return `Deadline: ${event.title}, due ${day} at ${formatTime(event.startsAt)}`;
  }
  const allDay = formatAllDay(event.startsAt, event.endsAt);
  const category = EVENT_CATEGORY_LABELS[event.category].split(" / ")[0];
  const when = allDay ? `, ${allDay}` : ` at ${formatTime(event.startsAt)}`;
  return `${category}: ${event.title}, ${day}${when}`;
}
