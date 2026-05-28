import type { CampusEvent } from "@/types/event";

export const CATEGORY_RAIL: Record<CampusEvent["category"], string> = {
  club: "bg-highlander",
  academic: "bg-leaf",
  social: "bg-coral",
  career: "bg-ink",
  sports: "bg-sky",
  arts: "bg-plum",
  community: "bg-sage",
  free_food: "bg-gold",
};
