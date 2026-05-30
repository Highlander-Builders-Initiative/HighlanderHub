import type { EventRow } from "@/lib/supabase-rows";
import { sanitizePublicEventHost } from "@/lib/events/anonymized-hosts";
import { normalizeHttpUrl } from "@/lib/events/validation";
import type { CampusEvent } from "@/types/event";

/** DB snake_case row → app `CampusEvent` (shared by feed and admin). */
export function eventRowToCampusEvent(r: EventRow): CampusEvent {
  const { host, hostHandle } = sanitizePublicEventHost(r.host, r.host_handle);
  return {
    id: r.id,
    title: r.title,
    description: r.description,
    startsAt: r.starts_at,
    endsAt: r.ends_at ?? undefined,
    location: r.location,
    host,
    hostHandle,
    category: r.category,
    contentKind: r.content_kind,
    tags: r.tags,
    source: r.source,
    sourceUrl: normalizeHttpUrl(r.source_url) ?? undefined,
    imageUrl: normalizeHttpUrl(r.image_url) ?? undefined,
    isFree: r.is_free,
    rsvpRequired: r.rsvp_required,
    rsvpUrl: normalizeHttpUrl(r.rsvp_url) ?? undefined,
    scrapedAt: r.scraped_at,
  };
}
