import type { EventRow } from "@/lib/supabase-rows";
import { publicEventHosts } from "@/lib/events/anonymized-hosts";
import { normalizeHttpUrl } from "@/lib/events/validation";
import { coerceEventCategory, type CampusEvent } from "@/types/event";

/**
 * A row as read back: the upsert shape plus the columns the database derives,
 * which no writer sends.
 */
export type StoredEventRow = EventRow & {
  /** When the listing starts or is due; see the event_sort_at migration. */
  sort_at: string;
};

/** DB snake_case row → app `CampusEvent` (shared by feed and admin). */
export function eventRowToCampusEvent(r: StoredEventRow): CampusEvent {
  const hosts = publicEventHosts(r);
  return {
    id: r.id,
    title: r.title,
    description: r.description,
    startsAt: r.starts_at,
    endsAt: r.ends_at ?? undefined,
    sortAt: r.sort_at,
    location: r.location,
    host: hosts.map((entry) => entry.host || entry.hostHandle).join(" & "),
    hostHandle: hosts[0]?.hostHandle,
    hosts,
    category: coerceEventCategory(r.category),
    contentKind: r.content_kind,
    tags: r.tags,
    source: r.source,
    sourceUrl: normalizeHttpUrl(r.source_url) ?? undefined,
    imageUrl: normalizeHttpUrl(r.image_url) ?? undefined,
    hasFreeFood: r.has_free_food,
    rsvpRequired: r.rsvp_required,
    rsvpUrl: normalizeHttpUrl(r.rsvp_url) ?? undefined,
    scrapedAt: r.scraped_at,
  };
}
