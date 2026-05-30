/**
 * Saved-events storage contract. Saves live in the browser (localStorage), not
 * in an account — a per-device "things I want to check out" list that needs no
 * sign-in, matching the no-account principle in PRODUCT.md. These helpers are
 * pure (no `window`) so they stay unit-testable; the React binding lives in
 * `useSavedEvents`.
 */
export const SAVED_EVENTS_KEY = "hh:saved-events:v1";

// A generous ceiling so a runaway writer can't bloat localStorage; far beyond
// any realistic personal shortlist.
const MAX_SAVED = 500;

/** Parse a raw localStorage value into a clean, deduped list of event ids. */
export function parseSavedIds(raw: string | null | undefined): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const seen = new Set<string>();
    for (const value of parsed) {
      if (typeof value === "string" && value && !seen.has(value)) {
        seen.add(value);
        if (seen.size >= MAX_SAVED) break;
      }
    }
    return [...seen];
  } catch {
    return [];
  }
}

export function serializeSavedIds(ids: string[]): string {
  return JSON.stringify(ids);
}

/** Add the id if absent, remove it if present. Newest saves go to the front. */
export function toggleSavedId(ids: string[], id: string): string[] {
  if (ids.includes(id)) return ids.filter((value) => value !== id);
  return [id, ...ids].slice(0, MAX_SAVED);
}
