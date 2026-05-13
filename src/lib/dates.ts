// UCR is Pacific. ISO timestamps in the DB are UTC, but the UI must group
// and filter by Pacific calendar days — otherwise late-evening events leak
// into the next day's bucket.
const CAMPUS_TZ = "America/Los_Angeles";

const dayKeyFmt = new Intl.DateTimeFormat("en-CA", {
  timeZone: CAMPUS_TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** YYYY-MM-DD in campus (Pacific) local time, derived from an ISO instant. */
export function pacificDayKey(iso: string): string {
  return dayKeyFmt.format(new Date(iso));
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
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

export function formatDayShort(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  return d
    .toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
    })
    .toLowerCase()
    .replace(" ", "");
}

export function formatTimeRange(startIso: string, endIso?: string): string {
  const start = formatTime(startIso);
  if (!endIso) return start;
  return `${start} – ${formatTime(endIso)}`;
}

export function relativeDay(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(d);
  target.setHours(0, 0, 0, 0);
  const diffDays = Math.round(
    (target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24)
  );
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  if (diffDays > 1 && diffDays < 7) {
    return d.toLocaleDateString("en-US", { weekday: "long" });
  }
  return formatDayShort(iso);
}
