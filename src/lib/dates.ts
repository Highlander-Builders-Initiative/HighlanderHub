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
const monthYearFmt = new Intl.DateTimeFormat("en-US", {
  timeZone: CAMPUS_TZ,
  month: "long",
  year: "numeric",
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

function parseDayKey(dayKey: string): { year: number; month: number; day: number } {
  const [year, month, day] = dayKey.split("-").map(Number);
  return { year, month, day };
}

function dayKeyToNoonUtc(dayKey: string): Date {
  const { year, month, day } = parseDayKey(dayKey);
  return new Date(Date.UTC(year, month - 1, day, 12));
}

function pacificMidnightMs(iso: string): number {
  return Date.parse(`${pacificDayKey(iso)}T00:00:00Z`);
}

export function pacificTodayKey(now = new Date()): string {
  return pacificDayKey(now.toISOString());
}

export function startOfPacificMonthKey(dayKey: string): string {
  const { year, month } = parseDayKey(dayKey);
  return `${year}-${String(month).padStart(2, "0")}-01`;
}

export function addPacificDays(dayKey: string, days: number): string {
  const date = dayKeyToNoonUtc(dayKey);
  date.setUTCDate(date.getUTCDate() + days);
  return dayKeyFmt.format(date);
}

export function addPacificMonths(monthKey: string, months: number): string {
  const { year, month } = parseDayKey(monthKey);
  return dayKeyFmt.format(new Date(Date.UTC(year, month - 1 + months, 1, 12)));
}

export function pacificWeekdayIndex(dayKey: string): number {
  return dayKeyToNoonUtc(dayKey).getUTCDay();
}

export function pacificDayOfMonth(dayKey: string): number {
  return parseDayKey(dayKey).day;
}

export function formatPacificDayKey(dayKey: string): string {
  return fullDayFmt.format(dayKeyToNoonUtc(dayKey));
}

export function formatPacificMonth(dayKey: string): string {
  return monthYearFmt.format(dayKeyToNoonUtc(dayKey));
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
