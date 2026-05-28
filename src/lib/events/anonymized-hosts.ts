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
