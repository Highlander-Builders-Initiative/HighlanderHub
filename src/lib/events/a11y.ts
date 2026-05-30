import type { CampusEvent } from "@/types/event";
import { EVENT_CATEGORY_LABELS } from "@/types/event";
import { isDeadlineKind } from "@/lib/events/content-kind";
import { formatTime, relativeDay } from "@/lib/dates";

/** Link name for mosaic / marquee tiles (title + day, no time). */
export function eventTileLinkLabel(event: CampusEvent): string {
  return `${event.title}, ${relativeDay(event.startsAt)}`;
}

/** Image alt when the flyer sits inside a link that already has eventTileLinkLabel. */
export function eventFlyerAlt(event: CampusEvent): string {
  return `${eventTileLinkLabel(event)} flyer`;
}

/**
 * Link name for list / calendar rows. Leads with category because the visible
 * card carries category only as a color tint on the time column, which is
 * invisible to AT.
 */
export function eventListLinkLabel(event: CampusEvent): string {
  if (isDeadlineKind(event.contentKind)) {
    return `Deadline: ${event.title}, due ${relativeDay(event.startsAt)} at ${formatTime(
      event.startsAt
    )}`;
  }
  const category = EVENT_CATEGORY_LABELS[event.category].split(" / ")[0];
  return `${category}: ${event.title}, ${relativeDay(event.startsAt)} at ${formatTime(
    event.startsAt
  )}`;
}
