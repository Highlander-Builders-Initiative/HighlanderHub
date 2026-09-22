import { track as vercelTrack } from "@vercel/analytics";

type Primitive = string | number | boolean | null;

export type HbiCtaLocation =
  | "hero"
  | "footer_social"
  | "footer_credit"
  | "about_page"
  | "editors_note";

type EventMap = {
  event_open: { id: string; category: string; surface: "list_card" | "mosaic_tile" | "calendar_card" };
  event_primary_cta: { id: string; kind: "rsvp" | "view_source"; surface: "desktop" | "mobile" };
  event_add_to_calendar: { id: string; surface: "desktop" | "mobile"; method: "google" | "ics" };
  event_share: { id: string; method: "native" | "clipboard" | "mailto"; surface: "text" | "icon" };
  events_search: { query_length: number };
  events_filter: { category: string };
  events_day_window: { window: "all" | "today" | "week" | "weekend" };
  events_calendar_jump: { day: string };
  events_clear_filters: Record<string, never>;
  hbi_cta_click: { location: HbiCtaLocation; channel: string };
};

export function track<K extends keyof EventMap>(
  name: K,
  props?: EventMap[K]
): void {
  vercelTrack(name, props as Record<string, Primitive> | undefined);
}
