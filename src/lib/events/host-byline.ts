type Host = { host: string; hostHandle?: string };

/** "A", "A & B", "A, B & C" */
export function joinHostNames(names: string[]): string {
  if (names.length < 2) return names[0] ?? "";
  return `${names.slice(0, -1).join(", ")} & ${names[names.length - 1]}`;
}

/** Hosts by their display names (the account label), handle as a fallback. */
export function hostNamesByline(hosts: readonly Host[]): string {
  return joinHostNames(hosts.map((host) => host.host || host.hostHandle || ""));
}

/**
 * Hosts by their Instagram handles ("acm_ucr"), for narrow screens where a
 * full club name truncates. Hosts without a handle keep their name.
 */
export function hostHandlesByline(hosts: readonly Host[]): string {
  return joinHostNames(
    hosts.map(
      (host) => host.hostHandle?.trim().replace(/^@/, "").toLowerCase() || host.host
    )
  );
}
