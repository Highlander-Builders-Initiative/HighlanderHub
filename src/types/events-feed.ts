import type { CampusEvent } from "./event";

export const DAY_WINDOWS = [
  // Short labels so the four windows sit side by side in the narrow rail. The
  // longer-form sentence copy lives in `phrase`, not `label`.
  { value: "all", label: "All", phrase: "" },
  { value: "today", label: "Today", phrase: "today" },
  { value: "week", label: "Week", phrase: "this week" },
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
  | "hostHandle"
  | "category"
  | "tags"
  | "hasFreeFood"
>;
