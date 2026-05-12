export type EventSource =
  | "instagram"
  | "highlander_link"
  | "campus_website"
  | "club_website"
  | "manual";

export type EventCategory =
  | "club"
  | "academic"
  | "social"
  | "career"
  | "sports"
  | "arts"
  | "community"
  | "free_food";

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
  tags: string[];
  source: EventSource;
  sourceUrl?: string;
  imageUrl?: string;
  isFree: boolean;
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
