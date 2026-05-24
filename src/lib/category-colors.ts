import type { CampusEvent } from "@/types/event";

export const CATEGORY_RAIL: Record<CampusEvent["category"], string> = {
  club: "bg-highlander",
  academic: "bg-leaf",
  social: "bg-coral",
  career: "bg-ink",
  sports: "bg-sky",
  arts: "bg-coral",
  community: "bg-leaf",
  free_food: "bg-gold",
};

// Soft category tint for chrome that fills a large area (the EventCard time
// column). Lower opacity than CategoryBadge's /10 because the surface is
// bigger; gold needs more saturation than the others to register at all.
export const CATEGORY_TIME_TINT: Record<CampusEvent["category"], string> = {
  club: "bg-highlander/[0.07]",
  academic: "bg-leaf/[0.08]",
  social: "bg-coral/[0.07]",
  career: "bg-ink/[0.05]",
  sports: "bg-sky/[0.07]",
  arts: "bg-coral/[0.07]",
  community: "bg-leaf/[0.08]",
  free_food: "bg-gold/[0.12]",
};
