export const DAY_WINDOWS = [
  { value: "all", label: "Anytime" },
  { value: "today", label: "Today" },
  { value: "week", label: "This week" },
  { value: "weekend", label: "Weekend" },
] as const;

export type DayWindow = (typeof DAY_WINDOWS)[number]["value"];
