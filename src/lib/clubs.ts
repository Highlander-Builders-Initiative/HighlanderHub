import accountsData from "../../pipeline/accounts.json";

export type Club = {
  handle: string;
  label: string;
  category: string;
};

const ALL_CLUBS: Club[] = (accountsData.accounts as Club[])
  .filter((a) => a.category === "club")
  .map((a) => ({ handle: a.handle, label: a.label, category: a.category }))
  .sort((a, b) => a.label.localeCompare(b.label));

export function searchClubs(query: string, limit = 8): Club[] {
  const q = query.trim().toLowerCase();
  if (!q) return ALL_CLUBS.slice(0, limit);

  const scored: Array<{ club: Club; score: number }> = [];
  for (const club of ALL_CLUBS) {
    const label = club.label.toLowerCase();
    const handle = club.handle.toLowerCase();
    let score = -1;
    if (label.startsWith(q) || handle.startsWith(q)) score = 3;
    else if (label.includes(` ${q}`) || handle.includes(`_${q}`)) score = 2;
    else if (label.includes(q) || handle.includes(q)) score = 1;
    if (score >= 0) scored.push({ club, score });
  }
  scored.sort((a, b) => b.score - a.score || a.club.label.localeCompare(b.club.label));
  return scored.slice(0, limit).map((s) => s.club);
}

export function clubInitials(label: string): string {
  const cleaned = label.replace(/[@_.]/g, " ").trim();
  const parts = cleaned.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}
