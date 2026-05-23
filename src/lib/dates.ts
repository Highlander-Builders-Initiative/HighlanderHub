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
const monthDayFmt = new Intl.DateTimeFormat("en-US", {
  timeZone: CAMPUS_TZ,
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
const wallTimeFmt = new Intl.DateTimeFormat("en-US", {
  timeZone: "UTC",
  hour: "numeric",
  minute: "2-digit",
});
const pacificDateTimePartsFmt = new Intl.DateTimeFormat("en-US", {
  timeZone: CAMPUS_TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});
const dateTimeInputRe =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/;

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

export function formatPacificDayKeyShort(dayKey: string): string {
  return shortDayFmt.format(dayKeyToNoonUtc(dayKey));
}

export function formatPacificMonthDay(dayKey: string): string {
  return monthDayFmt.format(dayKeyToNoonUtc(dayKey));
}

export function formatPacificMonth(dayKey: string): string {
  return monthYearFmt.format(dayKeyToNoonUtc(dayKey));
}

export function formatWallClockTime(timeInput: string): string {
  const match = /^(\d{2}):(\d{2})$/.exec(timeInput);
  if (!match) return "";

  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour > 23 || minute > 59) return "";

  return wallTimeFmt.format(new Date(Date.UTC(2000, 0, 1, hour, minute)));
}

function pacificParts(date: Date) {
  const parts = pacificDateTimePartsFmt.formatToParts(date);
  const get = (type: string) =>
    Number(parts.find((part) => part.type === type)?.value ?? NaN);

  return {
    year: get("year"),
    month: get("month"),
    day: get("day"),
    hour: get("hour"),
    minute: get("minute"),
    second: get("second"),
  };
}

function partsAsUtcMs(parts: ReturnType<typeof pacificParts>): number {
  return Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour,
    parts.minute,
    parts.second
  );
}

function sameParts(
  left: ReturnType<typeof pacificParts>,
  right: ReturnType<typeof pacificParts>
): boolean {
  return (
    left.year === right.year &&
    left.month === right.month &&
    left.day === right.day &&
    left.hour === right.hour &&
    left.minute === right.minute &&
    left.second === right.second
  );
}

export function parsePacificDateTimeInput(value: unknown): string | null {
  if (typeof value !== "string") return null;

  const match = dateTimeInputRe.exec(value.trim());
  if (!match) return null;

  const target = {
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3]),
    hour: Number(match[4]),
    minute: Number(match[5]),
    second: Number(match[6] ?? 0),
  };

  if (
    target.month < 1 ||
    target.month > 12 ||
    target.day < 1 ||
    target.day > 31 ||
    target.hour > 23 ||
    target.minute > 59 ||
    target.second > 59
  ) {
    return null;
  }

  const targetAsUtc = partsAsUtcMs(target);
  let utcMs = targetAsUtc;

  for (let i = 0; i < 3; i += 1) {
    const renderedAsUtc = partsAsUtcMs(pacificParts(new Date(utcMs)));
    const diff = targetAsUtc - renderedAsUtc;
    if (diff === 0) break;
    utcMs += diff;
  }

  const instant = new Date(utcMs);
  return sameParts(pacificParts(instant), target) ? instant.toISOString() : null;
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

export function formatUpcomingWeekLabel(count: number | null): string | null {
  if (count === null) return null;
  if (count === 0) return "nothing posted yet this week";
  if (count === 1) return "1 event this week";
  return `${count} events this week`;
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
