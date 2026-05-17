import { track as vercelTrack } from "@vercel/analytics";

type Primitive = string | number | boolean | null;

type EventMap = {
  event_open: { id: string; category: string; surface: "list_card" | "mosaic_tile" | "calendar_card" };
  event_primary_cta: { id: string; kind: "rsvp" | "view_source"; surface: "desktop" | "mobile" };
  event_add_to_calendar: { id: string; surface: "desktop" | "mobile" };
  event_share: { id: string; method: "native" | "clipboard" | "mailto"; surface: "text" | "icon" };
  events_search: { query_length: number };
  events_filter: { category: string };
  events_view_toggle: { view: "list" | "calendar" };
  events_clear_filters: Record<string, never>;
  hbi_cta_click: { location: "hero" | "footer_social"; channel: string };
  submit_cta_click: { surface: "events_header" | "empty_state" };
  submission_start: Record<string, never>;
  submission_complete: Record<string, never>;
  submission_error: { message: string };
};

export function track<K extends keyof EventMap>(
  name: K,
  props?: EventMap[K]
): void {
  vercelTrack(name, props as Record<string, Primitive> | undefined);
}
