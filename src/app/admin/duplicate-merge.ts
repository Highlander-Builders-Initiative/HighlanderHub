import { pacificDayKey } from "@/lib/dates";
import { isAnonymizedHostHandle } from "@/lib/events/anonymized-hosts";
import type { AdminEventRow } from "./types";

type Host = { host: string; host_handle: string };

/** Details a merge may combine into the kept event (see merge_duplicate_events). */
export type DuplicateMergeChanges = Partial<
  Pick<
    AdminEventRow,
    | "has_free_food"
    | "rsvp_required"
    | "starts_at"
    | "all_day"
    | "ends_at"
    | "rsvp_url"
    | "image_url"
    | "image_is_video"
    | "location"
  > & { hosts: Host[]; is_locked: true }
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
 * merge_duplicate_events RPC accepts. `starts_at` stands for the whole date
 * and time: the start, its end and whether it is date-only move together.
 */
export const MERGE_FIELD_CHOICES = [
  "starts_at",
  "location",
  "ends_at",
  "image_url",
  "rsvp_url",
] as const;
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

/** Whether the two listings give the event a different date, time or precision. */
function differentTime(kept: AdminEventRow, removed: AdminEventRow): boolean {
  return (
    !sameInstant(kept.starts_at, removed.starts_at) ||
    Boolean(kept.all_day) !== Boolean(removed.all_day)
  );
}

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
      case "starts_at":
        return differentTime(kept, removed);
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
 * host's RSVP link carries over. A date-only listing takes the other's time
 * of day on the same date; a different date or time is the admin's call.
 */
export function defaultMergeTakes(
  kept: AdminEventRow,
  removed: AdminEventRow
): MergeFieldChoice[] {
  return mergeFieldOptions(kept, removed).filter((field) => {
    switch (field) {
      case "starts_at":
        return (
          Boolean(kept.all_day) &&
          !removed.all_day &&
          pacificDayKey(kept.starts_at) === pacificDayKey(removed.starts_at)
        );
      case "location":
        return VAGUE_LOCATION.test(kept.location) && !VAGUE_LOCATION.test(removed.location);
      case "ends_at":
        return !kept.ends_at;
      case "image_url":
        // A video's cover frame is no flyer: the other listing's still replaces it.
        return !kept.image_url || (kept.image_is_video === true && removed.image_is_video !== true);
      case "rsvp_url":
        return !kept.rsvp_url && sameHost(kept, removed);
    }
  });
}

// The other listing's date and time bring their own end, so a separate
// choice of end means nothing once they are taken.
const effectiveTakes = (takes: readonly MergeFieldChoice[]) =>
  takes.filter((field) => !(field === "ends_at" && takes.includes("starts_at")));

/**
 * Whether the merge must lock the kept listing so the next import keeps the
 * admin's choices. The kept listing's own post republishes it on every
 * import, and reconciliation then combines the two posts by its own rules,
 * which are the defaults here. Any choice that differs from them (taking a
 * detail the kept listing already has, or declining one it lacks) would be
 * undone, and so would any date and time, which only a reel's can replace.
 * A locked listing stops following its post, so defaults are left unlocked.
 */
export function mergeLocksListing(
  kept: AdminEventRow,
  removed: AdminEventRow,
  takes: readonly MergeFieldChoice[] = defaultMergeTakes(kept, removed)
): boolean {
  if (kept.is_locked) return false;
  const options = mergeFieldOptions(kept, removed);
  const chosen = effectiveTakes(options.filter((field) => takes.includes(field)));
  const defaults = effectiveTakes(defaultMergeTakes(kept, removed));
  return (
    chosen.includes("starts_at") ||
    chosen.length !== defaults.length ||
    chosen.some((field) => !defaults.includes(field))
  );
}

/**
 * What the kept listing takes from the one merged into it, and a phrase for
 * each addition. The kept listing keeps its own title. Free food and co-hosts
 * always carry over; date and time, venue, end time, flyer and RSVP link come
 * from the other listing when `takes` names them (by default, only where the
 * kept listing lacks them; see defaultMergeTakes). A field that is not one of
 * mergeFieldOptions is ignored.
 *
 * Taking the date and time takes the other listing's end with it (or none):
 * the kept listing's end belongs to the time being replaced. Choices the next
 * import would undo lock the kept listing (see mergeLocksListing).
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
    // Whether the image is a video's cover frame travels with the image.
    if ((removed.image_is_video ?? null) !== (kept.image_is_video ?? null)) {
      changes.image_is_video = removed.image_is_video ?? null;
    }
    additions.push("flyer");
  }

  if (taking("starts_at")) {
    changes.starts_at = removed.starts_at;
    changes.all_day = removed.all_day ?? null;
    changes.ends_at = removed.ends_at ?? null;
    additions.push("date and time");
  } else if (taking("ends_at")) {
    changes.ends_at = removed.ends_at;
    additions.push("end time");
  }

  if (taking("location")) {
    changes.location = removed.location;
    additions.push(`venue (${removed.location})`);
  }

  if (mergeLocksListing(kept, removed, takes)) changes.is_locked = true;

  return { changes, additions };
}
