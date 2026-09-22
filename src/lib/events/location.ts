/**
 * Locations are free text read off flyers, so "online" is inferred from the
 * wording: an online platform or keyword, with no physical venue left over
 * once links, platform names and filler are removed. Hybrid entries
 * ("CE-CERT Room 105 & Zoom") name a room you can walk into, so they stay
 * in-person. Unrecognized leftovers fall back to in-person too.
 */
const ONLINE_TERMS =
  /\b(?:zoom|google meet|gmeet|microsoft teams|ms teams|webex|discord|twitch|youtube(?: live)?|instagram live|ig live|live ?stream(?:ed|ing)?|online|virtual(?:ly)?|remote(?:ly)?)\b/gi;

const LINKS =
  /(?:https?:\/\/\S+|\S+\.(?:com|us|gg|tv|be|me|org|edu|net|io)\b\S*)/gi;

const FILLER = new Set([
  "a", "and", "at", "be", "bio", "call", "check", "code", "id", "in", "link",
  "links", "linktree", "live", "meeting", "only", "or", "our", "over",
  "passcode", "password", "pwd", "see", "server", "tba", "tbd", "the", "via",
]);

export function isOnlineLocation(location: string | null | undefined): boolean {
  if (!location) return false;
  if (!location.match(ONLINE_TERMS)) return false;

  const leftover = location
    .replace(LINKS, " ")
    .replace(ONLINE_TERMS, " ")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((token) => token && !/^\d+$/.test(token) && !FILLER.has(token));

  return leftover.length === 0;
}
