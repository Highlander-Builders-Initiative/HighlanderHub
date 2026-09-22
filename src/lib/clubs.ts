import accountsData from "../../pipeline/accounts.json";
import accountActivity from "../../pipeline/data/account_activity.json";
import { isAnonymizedHostHandle } from "@/lib/events/anonymized-hosts";

export type Club = {
  handle: string;
  label: string;
  category: string;
};

type ClubHost = { host: string; hostHandle?: string; category: string;
  hosts?: { host: string; hostHandle?: string }[] };

export function getClubs(hosts: readonly ClubHost[] = []): Club[] {
  const clubs = new Map<string, Club>();
  for (const handle of Object.keys(accountActivity)) {
    clubs.set(handle, { handle, label: handle, category: "club" });
  }
  for (const { handle, label, category } of accountsData.accounts) {
    clubs.set(handle, { handle, label, category });
  }
  // Use the full public event source, not just the currently loaded feed page.
  for (const { host, hostHandle, category } of hosts.flatMap((event) =>
    event.hosts?.length ? event.hosts.map((host) => ({ ...host, category: event.category })) : [event]
  )) {
    const handle = (hostHandle ?? "").trim().replace(/^@/, "").toLowerCase();
    if (!handle) continue;
    const existing = clubs.get(handle);
    if (!existing || existing.label === handle) {
      clubs.set(handle, { handle, label: host.trim() || handle, category });
    }
  }
  return [...clubs.values()]
    .filter((club) => !isAnonymizedHostHandle(club.handle))
    .sort((a, b) => a.label.localeCompare(b.label));
}

const ALL_CLUBS = getClubs();

export function searchClubs(query: string, limit = 8, clubs = ALL_CLUBS): Club[] {
  const q = query.trim().replace(/^@/, "").toLowerCase();
  if (!q) return clubs.slice(0, limit);

  const scored: Array<{ club: Club; score: number }> = [];
  for (const club of clubs) {
    const label = club.label.toLowerCase();
    const handle = club.handle.toLowerCase();
    let score = -1;
    if (label === q || handle === q) score = 4;
    else if (label.startsWith(q) || handle.startsWith(q)) score = 3;
    else if (label.includes(` ${q}`) || handle.includes(`_${q}`)) score = 2;
    else if (label.includes(q) || handle.includes(q)) score = 1;
    if (score >= 0) scored.push({ club, score });
  }
  scored.sort((a, b) => b.score - a.score || a.club.label.localeCompare(b.club.label));
  return scored.slice(0, limit).map((s) => s.club);
}
