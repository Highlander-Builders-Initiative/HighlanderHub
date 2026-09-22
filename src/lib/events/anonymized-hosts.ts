/** Instagram handles whose scraped events must not show a public host name. */
const ANONYMIZED_HOST_HANDLES = new Set(["highlander_opps"]);

function normalizeHandle(handle: string | null | undefined): string {
  return (handle ?? "").trim().replace(/^@/, "").toLowerCase();
}

export function isAnonymizedHostHandle(
  hostHandle: string | null | undefined
): boolean {
  const normalized = normalizeHandle(hostHandle);
  return normalized !== "" && ANONYMIZED_HOST_HANDLES.has(normalized);
}

/** Strip host display for accounts that requested anonymity. */
export function sanitizePublicEventHost(
  host: string,
  hostHandle?: string | null
): { host: string; hostHandle?: string } {
  if (!isAnonymizedHostHandle(hostHandle)) {
    return { host, hostHandle: hostHandle ?? undefined };
  }
  return { host: "", hostHandle: undefined };
}

/** Preserve each club's identity while hiding private hosts in merged events. */
export function publicEventHosts(row: {
  host: string;
  host_handle?: string | null;
  hosts?: { host: string; host_handle: string }[];
}): { host: string; hostHandle?: string }[] {
  const hosts = new Map<string, { host: string; hostHandle?: string }>();
  for (const entry of [row, ...(row.hosts ?? [])]) {
    const host = sanitizePublicEventHost(entry.host, entry.host_handle);
    const key = normalizeHandle(host.hostHandle) || host.host.trim().toLowerCase();
    if (key && !hosts.has(key)) hosts.set(key, host);
  }
  return [...hosts.values()];
}
