import type { CampusEvent } from "@/types/event";

/**
 * In-memory handoff from a list card to /events/[id]. The card already holds
 * the full event, so the detail route's loading state can render the real page
 * immediately instead of a skeleton while the server round-trip is in flight.
 *
 * Memory only, on purpose: loading UI only shows during client navigation, and
 * a hard load should never paint a stale copy before the server's.
 */

const MAX_HANDOFFS = 20;
const handoff = new Map<string, CampusEvent>();

export function stashEventForDetail(event: CampusEvent) {
  if (typeof window === "undefined") return;

  handoff.delete(event.id);
  handoff.set(event.id, event);
  if (handoff.size > MAX_HANDOFFS) {
    const oldest = handoff.keys().next().value;
    if (oldest !== undefined) handoff.delete(oldest);
  }
}

export function peekEventForDetail(id: string): CampusEvent | null {
  return handoff.get(id) ?? null;
}
