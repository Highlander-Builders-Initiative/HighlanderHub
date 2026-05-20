import type { EventCategory, EventSource } from "@/lib/supabase-rows";

export type { EventCategory, EventSource };

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
