import {
  EVENT_CATEGORIES,
  type EventCategory,
  type EventContentKind,
  type EventSource,
} from "@/lib/supabase-rows";

export { EVENT_CATEGORIES };
export type { EventCategory, EventContentKind, EventSource };

export const EVENT_CATEGORY_LABELS: Record<EventCategory, string> = {
  club: "Club / org",
  academic: "Academic / lecture",
  social: "Social",
  career: "Career / professional",
  sports: "Sports / athletics",
  arts: "Arts / performance",
  community: "Community / service",
  free_food: "Free food",
};

export interface CampusEvent {
  id: string;
  title: string;
  description: string;
  startsAt: string; // ISO date string
  endsAt?: string;
  location: string;
  host: string; // club, dept, or org running it
  hostHandle?: string; // @instagram or similar
  category: EventCategory;
  contentKind: EventContentKind;
  tags: string[];
  source: EventSource;
  sourceUrl?: string;
  imageUrl?: string;
  isFree: boolean;
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
