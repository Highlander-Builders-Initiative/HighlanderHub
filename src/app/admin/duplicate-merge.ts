import { pacificDayKey } from "@/lib/dates";
import { isAnonymizedHostHandle } from "@/lib/events/anonymized-hosts";
import type { AdminEventRow } from "./types";

type Host = { host: string; host_handle: string };

/** Details a merge may combine into the kept event (see merge_duplicate_events). */
export type DuplicateMergeChanges = Partial<
  Pick<
    AdminEventRow,
    "has_free_food" | "rsvp_required" | "ends_at" | "rsvp_url" | "image_url" | "location"
  > & { hosts: Host[] }
>;

// Placeholders and the campus default name no venue.
const VAGUE_LOCATION =
  /^\s*(?:|uc riverside|ucr|university of california,? riverside|tba|tbd|to be (?:announced|determined))\s*$|\b(?:tba|tbd)\b/i;

function handleOf(row: { host_handle?: string | null }): string {
  return (row.host_handle ?? "").trim().replace(/^@/, "").toLowerCase();
}

function sameHost(a: AdminEventRow, b: AdminEventRow): boolean {
  if (handleOf(a) && handleOf(b)) return handleOf(a) === handleOf(b);
  const name = a.host.trim().toLowerCase();
  return name !== "" && name === b.host.trim().toLowerCase();
}

function namedHosts(rows: AdminEventRow[]): Host[] {
  const hosts = new Map<string, Host>();
  for (const row of rows) {
    for (const entry of [row, ...(row.hosts ?? [])]) {
      const handle = handleOf(entry);
      if (!handle || isAnonymizedHostHandle(handle) || hosts.has(handle)) continue;
      hosts.set(handle, { host: entry.host || handle, host_handle: handle });
    }
  }
  return [...hosts.values()];
}

/**
 * What the kept listing takes from the one merged into it, and a phrase for
 * each addition. The kept listing keeps its own title, time, venue and
 * signup; the other only fills what it lacks, as reconciliation's
 * merge_duplicates does. A partner's signup can target another audience, so
 * only the same host's RSVP carries over.
 */
export function duplicateMergeChanges(
  kept: AdminEventRow,
  removed: AdminEventRow
): { changes: DuplicateMergeChanges; additions: string[] } {
  const changes: DuplicateMergeChanges = {};
  const additions: string[] = [];

  if (removed.has_free_food && !kept.has_free_food) {
    changes.has_free_food = true;
    additions.push("free food");
  }

  const keptHosts = namedHosts([kept]);
  const hosts = namedHosts([kept, removed]);
  if (hosts.length > keptHosts.length && (hosts.length > 1 || kept.hosts?.length)) {
    changes.hosts = hosts;
    for (const host of hosts.slice(keptHosts.length)) {
      additions.push(`co-host @${host.host_handle}`);
    }
  }

  if (sameHost(kept, removed)) {
    if (removed.rsvp_required && !kept.rsvp_required) {
      changes.rsvp_required = true;
      additions.push("RSVP required");
    }
    if (removed.rsvp_url && !kept.rsvp_url) {
      changes.rsvp_url = removed.rsvp_url;
      additions.push("RSVP link");
    }
  }

  if (removed.image_url && !kept.image_url) {
    changes.image_url = removed.image_url;
    additions.push("flyer");
  }

  // An end time only belongs to the same day, and a date-only listing's end
  // is a day boundary, not a time.
  if (
    removed.ends_at &&
    !kept.ends_at &&
    Date.parse(removed.ends_at) > Date.parse(kept.starts_at) &&
    pacificDayKey(removed.starts_at) === pacificDayKey(kept.starts_at) &&
    !(removed.all_day && !kept.all_day)
  ) {
    changes.ends_at = removed.ends_at;
    additions.push("end time");
  }

  if (VAGUE_LOCATION.test(kept.location) && !VAGUE_LOCATION.test(removed.location)) {
    changes.location = removed.location;
    additions.push(`venue (${removed.location})`);
  }

  return { changes, additions };
}
