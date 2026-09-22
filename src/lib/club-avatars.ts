import manifest from "./club-avatars.json";
import { isAnonymizedHostHandle } from "@/lib/events/anonymized-hosts";

/**
 * Club profile pictures are pre-sized 128px squares committed under
 * `public/club-avatars/<handle>.webp` by `pipeline/club_avatars.py`. The
 * manifest lists which handles have one (and where it came from), so a club
 * without a picture renders its monogram immediately instead of a 404.
 */
const AVATARS: Readonly<Record<string, string>> = manifest.avatars;

function normalizeHandle(handle: string | null | undefined): string {
  return (handle ?? "").trim().replace(/^@/, "").toLowerCase();
}

export function clubAvatarSrc(handle: string | null | undefined): string | undefined {
  const key = normalizeHandle(handle);
  if (!key || isAnonymizedHostHandle(key)) return undefined;
  if (!Object.prototype.hasOwnProperty.call(AVATARS, key)) return undefined;
  return `/club-avatars/${key}.webp`;
}

export function clubInitials(label: string): string {
  const skip = new Set(["at", "of", "de", "the", "and", "for", "in"]);
  const cleaned = label.replace(/[@_.]/g, " ").trim();
  const parts = cleaned
    .split(/\s+/)
    .filter((p) => p && !skip.has(p.toLowerCase()) && !/^\d+$/.test(p));
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}
