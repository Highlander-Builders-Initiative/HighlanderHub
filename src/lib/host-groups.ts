import accountsData from "./public-clubs.json";
import type { CampusEvent } from "@/types/event";

/**
 * Who hosts, as the feed's Hosted by filter groups it. This is a separate
 * question from the Topics (what you would be doing): a Chinese Student
 * Association boba night is a Hang out event hosted by a cultural org.
 */
export const HOST_GROUPS = [
  { value: "culture", label: "Cultural groups", phrase: "cultural groups" },
  { value: "faith", label: "Faith groups", phrase: "faith groups" },
  { value: "greek", label: "Greek life", phrase: "Greek life" },
  { value: "campus", label: "Campus offices", phrase: "campus offices" },
] as const;

export type HostGroup = (typeof HOST_GROUPS)[number]["value"];
export type HostGroupValue = HostGroup | "all";

/** Each account's HighlanderLink directory type, mapped onto a group. */
const GROUP_BY_DIRECTORY_TYPE: Partial<Record<string, HostGroup>> = {
  cultural: "culture",
  "spiritual-religious-atheist": "faith",
  "fraternity-sorority": "greek",
  "campus-department": "campus",
  "department-program": "campus",
  college: "campus",
};

// Campus offices that each serve one community (the ethnic student
// programs), and the office that runs Greek life, listed with the groups
// they serve rather than as campus offices.
const GROUP_BY_HANDLE_OVERRIDE: Record<string, HostGroup> = {
  apspucr: "culture",
  aspucr: "culture",
  csp_ucr: "culture",
  mescucr: "culture",
  naspucr: "culture",
  fsicucr: "greek",
};

const GROUP_BY_HANDLE = new Map<string, HostGroup>();
for (const { handle, category } of accountsData.accounts) {
  const group = GROUP_BY_HANDLE_OVERRIDE[handle] ?? GROUP_BY_DIRECTORY_TYPE[category];
  if (group) GROUP_BY_HANDLE.set(handle.toLowerCase(), group);
}

function normalizeHandle(handle: string | undefined): string {
  return (handle ?? "").trim().replace(/^@/, "").toLowerCase();
}

export function hostGroupLabel(value: HostGroupValue): string {
  return HOST_GROUPS.find((group) => group.value === value)?.label ?? "";
}

/** The group in a sentence: "events from faith groups". */
export function hostGroupPhrase(value: HostGroupValue): string {
  return HOST_GROUPS.find((group) => group.value === value)?.phrase ?? "";
}

export function coerceHostGroupParam(raw: string | undefined | null): HostGroupValue {
  return HOST_GROUPS.some((group) => group.value === raw)
    ? (raw as HostGroup)
    : "all";
}

/** An event belongs to every group one of its hosts is in. */
export function matchesHostGroup(
  event: Pick<CampusEvent, "hostHandle" | "hosts">,
  group: HostGroupValue
): boolean {
  if (group === "all") return true;
  const handles = event.hosts?.length
    ? event.hosts.map((host) => host.hostHandle)
    : [event.hostHandle];
  return handles.some((handle) => GROUP_BY_HANDLE.get(normalizeHandle(handle)) === group);
}
