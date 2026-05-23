import type { CampusEvent } from "./event";

export const DAY_WINDOWS = [
  { value: "all", label: "Anytime", phrase: "" },
  { value: "today", label: "Today", phrase: "today" },
  { value: "week", label: "This week", phrase: "this week" },
  { value: "weekend", label: "Weekend", phrase: "this weekend" },
] as const;

export type DayWindow = (typeof DAY_WINDOWS)[number]["value"];

export type EventFilterCountSource = Pick<
  CampusEvent,
  | "id"
  | "title"
  | "description"
  | "startsAt"
  | "location"
  | "host"
  | "category"
  | "tags"
>;
