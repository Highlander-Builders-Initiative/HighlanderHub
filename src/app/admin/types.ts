import type {
  EventCategory,
  EventContentKind,
} from "@/lib/supabase-rows";
import type { StoredEventRow } from "@/lib/events/map-event-row";
import { isPublicContentKind } from "@/lib/events/content-kind";
import { normalizeHttpUrl } from "@/lib/events/validation";

/** Live event row for admin (stored event row + DB moderation columns). */
export type AdminEventRow = StoredEventRow & {
  is_locked: boolean;
  created_at: string;
  updated_at: string;
};

/** A pending pair from the duplicate review queue; both listings are live. */
export type DuplicateReviewPair = {
  first: AdminEventRow;
  second: AdminEventRow;
};

export function duplicatePairKey(pair: DuplicateReviewPair): string {
  return `${pair.first.id}|${pair.second.id}`;
}

/** Writable event fields for admin edit (server allowlist). */
export const ADMIN_EVENT_UPDATE_KEYS = [
  "title",
  "description",
  "starts_at",
  "ends_at",
  "location",
  "host",
  "host_handle",
  "category",
  "content_kind",
  "image_url",
  "rsvp_url",
  "has_free_food",
  "rsvp_required",
] as const;

export type AdminEventUpdatePayload = {
  title: string;
  description: string;
  starts_at: string;
  ends_at: string | null;
  location: string;
  host: string;
  host_handle: string | null;
  category: EventCategory;
  content_kind: EventContentKind;
  image_url: string | null;
  rsvp_url: string | null;
  has_free_food: boolean;
  rsvp_required: boolean;
};

/** Same ordering as `getEventsPage` on the public /events feed. */
export function sortEventsByFeedOrder(events: AdminEventRow[]): AdminEventRow[] {
  return [...events].sort((a, b) => {
    const byTime = Date.parse(a.sort_at) - Date.parse(b.sort_at);
    if (byTime !== 0) return byTime;
    return a.id.localeCompare(b.id);
  });
}

// A post, reel or IGTV link names its media by shortcode; tracking
// parameters, slide indexes and the profile prefix vary between copies.
const INSTAGRAM_SHORTCODE = /instagram\.com\/(?:[\w.]+\/)?(?:p|reel|reels|tv)\/([\w-]+)/i;

/**
 * Whether a live listing matches the admin's search. A pasted Instagram link
 * finds the listing made from that post; "@handle" finds any listing that
 * names that account as host or co-host; other text matches title, host,
 * venue, description, handles, source link or id.
 */
export function matchesAdminQuery(query: string, event: AdminEventRow): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;

  const shortcode = INSTAGRAM_SHORTCODE.exec(q)?.[1];
  if (shortcode) {
    const own = INSTAGRAM_SHORTCODE.exec(event.source_url ?? "")?.[1];
    return own?.toLowerCase() === shortcode;
  }

  const handles = [event.host_handle, ...(event.hosts ?? []).map((h) => h.host_handle)]
    .filter((handle): handle is string => Boolean(handle))
    .map((handle) => handle.replace(/^@/, "").toLowerCase());
  if (/^@[\w.]+$/.test(q)) return handles.includes(q.slice(1));

  return [
    event.title,
    event.host,
    event.location,
    event.description,
    event.source_url,
    event.id,
    ...handles,
    ...(event.hosts ?? []).map((h) => h.host),
  ].some((field) => field?.toLowerCase().includes(q));
}

/** Quick filters for the live list; selected filters must all match. */
export const ADMIN_EVENT_FILTERS = [
  { key: "locked", label: "Locked", test: (e: AdminEventRow) => e.is_locked },
  {
    key: "hidden",
    label: "Hidden from public",
    test: (e: AdminEventRow) => !isPublicContentKind(e.content_kind),
  },
  {
    key: "no_flyer",
    label: "No flyer",
    test: (e: AdminEventRow) => !normalizeHttpUrl(e.image_url),
  },
  {
    // A deadline is a moment and an all-day listing ends at a day boundary,
    // so only a timed event can be missing its end.
    key: "no_end",
    label: "No end time",
    test: (e: AdminEventRow) =>
      !e.ends_at && !e.all_day && e.content_kind !== "student_deadline",
  },
] as const;

export type AdminEventFilterKey = (typeof ADMIN_EVENT_FILTERS)[number]["key"];
