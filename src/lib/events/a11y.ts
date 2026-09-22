import type { CampusEvent } from "@/types/event";
import { categoryShortLabel } from "@/types/event";
import { isDeadlineKind } from "@/lib/events/content-kind";
import { eventTimeLabel, relativeDay } from "@/lib/dates";

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
  const time = eventTimeLabel(event, "start");
  if (isDeadlineKind(event.contentKind)) {
    return `Deadline: ${event.title}, due ${day} at ${time}`;
  }
  return `${categoryShortLabel(event.category)}: ${event.title}, ${day}, ${time}`;
}
