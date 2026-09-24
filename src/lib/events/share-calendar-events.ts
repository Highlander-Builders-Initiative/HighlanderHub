import type { CampusEvent } from "@/types/event";
import type { EventFilterCountSource } from "@/types/events-feed";

type FeedLists = {
  events: CampusEvent[];
  filterCountSource: EventFilterCountSource[];
};

/** True when every field `entry` carries has the same value on `event`. */
function carriesSameFields(entry: object, event: CampusEvent): boolean {
  const fields = Object.keys(entry) as (keyof CampusEvent)[];
  return (
    JSON.stringify(entry) ===
    JSON.stringify(Object.fromEntries(fields.map((field) => [field, event[field]])))
  );
}

/**
 * /events hands the client three overlapping lists: the first feed page, the
 * filter-count source (every upcoming event) and the month calendar, so most
 * events used to be written into the page two or three times. The server
 * payload writes an object once and refers back to it wherever it appears
 * again, so this passes the calendar's object wherever a feed or count entry
 * is the same event. Entries swap only on an exact match (each list is cached
 * on its own and can briefly disagree after an edit), so the client receives
 * the same data. A count entry that becomes a full event only gains fields.
 */
export function shareCalendarEvents(
  calendarEvents: CampusEvent[],
  { events, filterCountSource }: FeedLists
): FeedLists {
  const calendarById = new Map(calendarEvents.map((event) => [event.id, event]));
  const share = <T extends { id: string }>(entry: T): T | CampusEvent => {
    const shared = calendarById.get(entry.id);
    return shared && carriesSameFields(entry, shared) ? shared : entry;
  };

  return {
    events: events.map(share),
    filterCountSource: filterCountSource.map(share),
  };
}
