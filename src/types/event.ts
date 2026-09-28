import {
  EVENT_CATEGORIES,
  type EventCategory,
  type EventContentKind,
  type EventSource,
} from "@/lib/supabase-rows";

export { EVENT_CATEGORIES };
export type { EventCategory, EventContentKind, EventSource };

/**
 * A category is what a student would be doing there. `other` is an event whose
 * text names no activity: it shows under All, never in a topic.
 */
export const EVENT_CATEGORY_LABELS: Record<EventCategory, string> = {
  hangout: "Hang out",
  get_involved: "Get involved",
  career: "Career & skills",
  academic: "Talks & learning",
  sports: "Sports & rec",
  arts: "Arts & shows",
  volunteering: "Volunteering",
  other: "Other",
};

const EVENT_CATEGORY_SHORT_LABELS: Record<EventCategory, string> = {
  hangout: "Hang out",
  get_involved: "Get involved",
  career: "Career",
  academic: "Learning",
  sports: "Sports",
  arts: "Arts",
  volunteering: "Volunteering",
  other: "Event",
};

/** "Career", "Learning", …: the one- or two-word name a card's tag wears. */
export function categoryShortLabel(category: EventCategory): string {
  return EVENT_CATEGORY_SHORT_LABELS[category];
}

/**
 * A stored category the app knows, else `other`. Rows written before the
 * activity categories ('club', 'social', …) read as uncategorized until the
 * pipeline rewrites them.
 */
export function coerceEventCategory(value: unknown): EventCategory {
  return (EVENT_CATEGORIES as readonly unknown[]).includes(value)
    ? (value as EventCategory)
    : "other";
}

export interface CampusEvent {
  id: string;
  title: string;
  description: string;
  startsAt: string; // ISO date string
  endsAt?: string;
  /**
   * When it starts or, for a deadline, is due: 11:59 PM on the due date when
   * the source gives only a date. The feed's order. Derived by the database.
   */
  sortAt: string;
  location: string;
  host: string; // club, dept, or org running it
  hostHandle?: string; // @instagram or similar
  hosts?: { host: string; hostHandle?: string }[];
  category: EventCategory;
  contentKind: EventContentKind;
  tags: string[];
  source: EventSource;
  sourceUrl?: string;
  imageUrl?: string;
  hasFreeFood: boolean;
  rsvpRequired: boolean;
  rsvpUrl?: string;
  scrapedAt: string; // ISO timestamp
}

export interface EventFilters {
  category?: EventCategory | "all";
  source?: EventSource | "all";
  freeFoodOnly?: boolean;
  query?: string;
}
