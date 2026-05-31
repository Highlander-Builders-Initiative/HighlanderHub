import {
  EVENT_CATEGORIES,
  type EventCategory,
  type EventContentKind,
  type EventSource,
} from "@/lib/supabase-rows";
import { EVENT_CONTENT_KIND_LABELS } from "@/lib/events/content-kind";

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

export const SUBMIT_EVENT_CATEGORIES = EVENT_CATEGORIES.map((value) => ({
  value,
  label: EVENT_CATEGORY_LABELS[value],
}));

/** Listing-type options for the public submit form (no fundraiser/other). */
export const SUBMIT_CONTENT_KINDS: { value: EventContentKind; label: string }[] =
  [
    { value: "student_event", label: EVENT_CONTENT_KIND_LABELS.student_event },
    {
      value: "student_deadline",
      label: EVENT_CONTENT_KIND_LABELS.student_deadline,
    },
  ];

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
