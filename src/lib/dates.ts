// UCR is Pacific. ISO timestamps in the DB are UTC, but the UI must group,
// filter, and display campus-facing dates in Pacific time — otherwise
// late-evening events drift into the next day's bucket depending on runtime TZ.
const CAMPUS_TZ = "America/Los_Angeles";
const MS_PER_DAY = 24 * 60 * 60 * 1000;

const dayKeyFmt = new Intl.DateTimeFormat("en-CA", {
  timeZone: CAMPUS_TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});
const fullDayFmt = new Intl.DateTimeFormat("en-US", {
  timeZone: CAMPUS_TZ,
  weekday: "long",
  month: "long",
  day: "numeric",
});
const shortDayFmt = new Intl.DateTimeFormat("en-US", {
  timeZone: CAMPUS_TZ,
  weekday: "short",
  month: "short",
  day: "numeric",
});
const weekdayFmt = new Intl.DateTimeFormat("en-US", {
  timeZone: CAMPUS_TZ,
  weekday: "long",
});
const timeFmt = new Intl.DateTimeFormat("en-US", {
  timeZone: CAMPUS_TZ,
  hour: "numeric",
  minute: "2-digit",
});

/** YYYY-MM-DD in campus (Pacific) local time, derived from an ISO instant. */
export function pacificDayKey(iso: string): string {
  return dayKeyFmt.format(new Date(iso));
}

function pacificMidnightMs(iso: string): number {
  return Date.parse(`${pacificDayKey(iso)}T00:00:00Z`);
}

/** The instant that was midnight in Pacific time on the current Pacific date. */
export function startOfPacificToday(): Date {
  const now = new Date();
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: CAMPUS_TZ,
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(now);
  const get = (t: string) =>
    Number(parts.find((p) => p.type === t)?.value ?? 0);
  const elapsed =
    (get("hour") * 60 * 60 + get("minute") * 60 + get("second")) * 1000;
  return new Date(now.getTime() - elapsed);
}

export function formatDay(iso: string): string {
  return fullDayFmt.format(new Date(iso));
}

export function formatDayShort(iso: string): string {
  return shortDayFmt.format(new Date(iso));
}

export function formatTime(iso: string): string {
  return timeFmt.format(new Date(iso)).toLowerCase().replace(/\s+/g, "");
}

export function formatTimeRange(startIso: string, endIso?: string): string {
  const start = formatTime(startIso);
  if (!endIso) return start;
  return `${start} – ${formatTime(endIso)}`;
}

export function relativeDay(iso: string): string {
  const today = pacificMidnightMs(new Date().toISOString());
  const target = pacificMidnightMs(iso);
  const diffDays = Math.round((target - today) / MS_PER_DAY);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  if (diffDays > 1 && diffDays < 7) {
    return weekdayFmt.format(new Date(iso));
  }
  return formatDayShort(iso);
}
