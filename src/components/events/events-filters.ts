import type { CampusEvent, EventCategory } from "@/types/event";
import {
  addPacificDays,
  pacificDayKey,
  pacificTodayKey,
  pacificWeekdayIndex,
} from "@/lib/dates";
import type { DayWindow } from "@/types/events-feed";

export type CategoryValue = EventCategory | "all";

export const CATEGORIES: { value: CategoryValue; label: string }[] = [
  { value: "all", label: "All" },
  { value: "club", label: "Clubs" },
  { value: "academic", label: "Academic" },
  { value: "social", label: "Social" },
  { value: "career", label: "Career" },
  { value: "sports", label: "Sports" },
  { value: "arts", label: "Arts" },
  { value: "community", label: "Community" },
  { value: "free_food", label: "Free Food" },
];

export { DAY_WINDOWS, type DayWindow } from "@/types/events-feed";

export function matchesCategory(
  ev: CampusEvent,
  cat: CategoryValue
): boolean {
  if (cat === "all") return true;
  if (cat === "free_food") {
    return ev.category === "free_food" || ev.tags.includes("free food");
  }
  return ev.category === cat;
}

/**
 * Returns the inclusive Pacific day-key range for a given window, anchored at
 * today. Returns null for "all" (no date constraint).
 */
export function dayWindowRange(
  window: DayWindow,
  today = pacificTodayKey()
): { start: string; end: string } | null {
  if (window === "all") return null;
  if (window === "today") return { start: today, end: today };
  if (window === "week") {
    // ISO-ish week starting Sunday (matches the calendar grid). Last day is
    // Saturday.
    const weekday = pacificWeekdayIndex(today); // 0=Sun
    const start = addPacificDays(today, -weekday);
    const end = addPacificDays(start, 6);
    // But "this week" should not include past days; pin start to today.
    return { start: today > start ? today : start, end };
  }
  // weekend: next Saturday + Sunday (or current weekend if today is Sat/Sun).
  const weekday = pacificWeekdayIndex(today);
  if (weekday === 0) return { start: today, end: today };
  if (weekday === 6) return { start: today, end: addPacificDays(today, 1) };
  const daysUntilSat = 6 - weekday;
  const start = addPacificDays(today, daysUntilSat);
  const end = addPacificDays(start, 1);
  return { start, end };
}

export function matchesDayWindow(
  ev: CampusEvent,
  window: DayWindow,
  today = pacificTodayKey()
): boolean {
  const range = dayWindowRange(window, today);
  if (!range) return true;
  const key = pacificDayKey(ev.startsAt);
  return key >= range.start && key <= range.end;
}
