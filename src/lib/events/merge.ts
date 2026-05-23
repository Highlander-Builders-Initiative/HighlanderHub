import type { CampusEvent } from "@/types/event";

export function mergeUniqueEventsByStart(
  current: CampusEvent[],
  incoming: CampusEvent[]
): CampusEvent[] {
  const merged = new Map(current.map((event) => [event.id, event]));
  for (const event of incoming) {
    if (!merged.has(event.id)) merged.set(event.id, event);
  }
  return Array.from(merged.values()).sort((a, b) => {
    const byStart = Date.parse(a.startsAt) - Date.parse(b.startsAt);
    return byStart === 0 ? a.id.localeCompare(b.id) : byStart;
  });
}
