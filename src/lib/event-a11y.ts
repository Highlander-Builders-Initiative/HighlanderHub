import type { CampusEvent } from "@/types/event";
import { formatTime, relativeDay } from "@/lib/dates";

/** Link name for mosaic / marquee tiles (title + day, no time). */
export function eventTileLinkLabel(event: CampusEvent): string {
  return `${event.title}, ${relativeDay(event.startsAt)}`;
}

/** Image alt when the flyer sits inside a link that already has eventTileLinkLabel. */
export function eventFlyerAlt(event: CampusEvent): string {
  return `${eventTileLinkLabel(event)} flyer`;
}

/** Link name for list / calendar rows (title + day + time). */
export function eventListLinkLabel(event: CampusEvent): string {
  return `${event.title}, ${relativeDay(event.startsAt)} at ${formatTime(
    event.startsAt
  )}`;
}
