import {
  addPacificDays,
  formatPacificDayKeyShort,
  formatPacificMonthDay,
  formatWallClockTime,
  pacificTodayKey,
  pacificWeekdayIndex,
} from "@/lib/dates";

export type EndChoice = "30m" | "1h" | "1h30" | "custom" | "none";

const END_CHOICE_MINUTES: Record<Exclude<EndChoice, "custom" | "none">, number> = {
  "30m": 30,
  "1h": 60,
  "1h30": 90,
};
const dateTimeInputRe = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/;

function padTwo(n: number): string {
  return String(n).padStart(2, "0");
}

function addMinutesToDateTimeInput(local: string, minutes: number): string {
  const match = dateTimeInputRe.exec(local);
  if (!match) return "";

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const ms = Date.UTC(year, month - 1, day, hour, minute);
  const date = new Date(ms);

  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day ||
    date.getUTCHours() !== hour ||
    date.getUTCMinutes() !== minute
  ) {
    return "";
  }

  date.setUTCMinutes(date.getUTCMinutes() + minutes);
  return [
    `${date.getUTCFullYear()}-${padTwo(date.getUTCMonth() + 1)}-${padTwo(
      date.getUTCDate()
    )}`,
    `${padTwo(date.getUTCHours())}:${padTwo(date.getUTCMinutes())}`,
  ].join("T");
}

export function submitTodayDateInput(now = new Date()): string {
  return pacificTodayKey(now);
}

export function submitTomorrowDateInput(now = new Date()): string {
  return addPacificDays(submitTodayDateInput(now), 1);
}

export function submitUpcomingFridayDateInput(now = new Date()): string {
  const today = submitTodayDateInput(now);
  const day = pacificWeekdayIndex(today);
  let delta = (5 - day + 7) % 7;
  if (delta <= 1) delta += 7;
  return addPacificDays(today, delta);
}

export function formatSubmitChipDate(input: string): string {
  return input ? formatPacificMonthDay(input) : "";
}

export function formatSubmitPreviewDateTime(local: string): string {
  if (!local) return "";

  const [dayKey, timeInput] = local.split("T");
  const day = formatPacificDayKeyShort(dayKey);
  const time = formatWallClockTime(timeInput);
  return day && time ? `${day} · ${time}` : "";
}

export function formatSubmitPreviewTime(local: string): string {
  if (!local) return "";

  const timeInput = local.split("T")[1] ?? "";
  return formatWallClockTime(timeInput);
}

export function computeSubmitEndsAtLocal(
  startsAtLocal: string,
  choice: EndChoice,
  customTime: string
): string {
  if (!startsAtLocal) return "";
  if (choice === "none") return "";
  if (choice === "custom") {
    if (!customTime) return "";
    return `${startsAtLocal.slice(0, 10)}T${customTime}`;
  }
  return addMinutesToDateTimeInput(startsAtLocal, END_CHOICE_MINUTES[choice]);
}
