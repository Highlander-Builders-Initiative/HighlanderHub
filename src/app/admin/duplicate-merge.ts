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
 * Details the admin may take from the removed listing instead of keeping the
 * kept one's, in the order the review shows them. Each is a column the
 * merge_duplicate_events RPC accepts.
 */
export const MERGE_FIELD_CHOICES = ["location", "ends_at", "image_url", "rsvp_url"] as const;
export type MergeFieldChoice = (typeof MERGE_FIELD_CHOICES)[number];

export function isMergeFieldChoice(value: unknown): value is MergeFieldChoice {
  return (MERGE_FIELD_CHOICES as readonly unknown[]).includes(value);
}

// An end time only belongs to the same day, and a date-only listing's end
// is a day boundary, not a time.
function usableEnd(kept: AdminEventRow, removed: AdminEventRow): boolean {
  return (
    Boolean(removed.ends_at) &&
    Date.parse(removed.ends_at!) > Date.parse(kept.starts_at) &&
    pacificDayKey(removed.starts_at) === pacificDayKey(kept.starts_at) &&
    !(removed.all_day && !kept.all_day)
  );
}

const sameInstant = (a: string | null | undefined, b: string | null | undefined) =>
  a && b ? Date.parse(a) === Date.parse(b) : !a && !b;

/**
 * Fields where the removed listing has a usable value that differs from the
 * kept one, so the admin has a real choice to make.
 */
export function mergeFieldOptions(
  kept: AdminEventRow,
  removed: AdminEventRow
): MergeFieldChoice[] {
  return MERGE_FIELD_CHOICES.filter((field) => {
    switch (field) {
      case "location":
        return (
          removed.location.trim() !== "" &&
          removed.location.trim().toLowerCase() !== kept.location.trim().toLowerCase()
        );
      case "ends_at":
        return usableEnd(kept, removed) && !sameInstant(kept.ends_at, removed.ends_at);
      case "image_url":
      case "rsvp_url":
        return Boolean(removed[field]) && removed[field] !== kept[field];
    }
  });
}

/**
 * The fields a merge takes when the admin makes no choice: the other listing
 * only fills what the kept one lacks, as reconciliation's merge_duplicates
 * does. A partner's signup can target another audience, so only the same
 * host's RSVP link carries over.
 */
export function defaultMergeTakes(
  kept: AdminEventRow,
  removed: AdminEventRow
): MergeFieldChoice[] {
  return mergeFieldOptions(kept, removed).filter((field) => {
    switch (field) {
      case "location":
        return VAGUE_LOCATION.test(kept.location) && !VAGUE_LOCATION.test(removed.location);
      case "ends_at":
        return !kept.ends_at;
      case "image_url":
        return !kept.image_url;
      case "rsvp_url":
        return !kept.rsvp_url && sameHost(kept, removed);
    }
  });
}

/**
 * What the kept listing takes from the one merged into it, and a phrase for
 * each addition. The kept listing keeps its own title and start time. Free
 * food and co-hosts always carry over; venue, end time, flyer and RSVP link
 * come from the other listing when `takes` names them (by default, only where
 * the kept listing lacks them; see defaultMergeTakes). A field that is not
 * one of mergeFieldOptions is ignored.
 */
export function duplicateMergeChanges(
  kept: AdminEventRow,
  removed: AdminEventRow,
  takes: readonly MergeFieldChoice[] = defaultMergeTakes(kept, removed)
): { changes: DuplicateMergeChanges; additions: string[] } {
  const changes: DuplicateMergeChanges = {};
  const additions: string[] = [];
  const options = mergeFieldOptions(kept, removed);
  const taking = (field: MergeFieldChoice) => takes.includes(field) && options.includes(field);

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

  // A signup requirement travels with the signup it describes.
  if (removed.rsvp_required && !kept.rsvp_required && (sameHost(kept, removed) || taking("rsvp_url"))) {
    changes.rsvp_required = true;
    additions.push("RSVP required");
  }
  if (taking("rsvp_url")) {
    changes.rsvp_url = removed.rsvp_url;
    additions.push("RSVP link");
  }

  if (taking("image_url")) {
    changes.image_url = removed.image_url;
    additions.push("flyer");
  }

  if (taking("ends_at")) {
    changes.ends_at = removed.ends_at;
    additions.push("end time");
  }

  if (taking("location")) {
    changes.location = removed.location;
    additions.push(`venue (${removed.location})`);
  }

  return { changes, additions };
}
