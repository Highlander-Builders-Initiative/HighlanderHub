import type { CampusEvent } from "@/types/event";

export const CATEGORY_RAIL: Record<CampusEvent["category"], string> = {
  club: "bg-tag-blue",
  academic: "bg-tag-violet",
  social: "bg-tag-coral",
  career: "bg-ink",
  sports: "bg-tag-cyan",
  arts: "bg-tag-magenta",
  community: "bg-tag-green",
  free_food: "bg-tag-amber",
};

/**
 * Tag and filter-pill colors. `highlight` is the pill background (a bright
 * category wash plus a matched hairline ring; the Topics rail slides it under
 * the selected row); `text` is the matched ink. Literal class strings so
 * Tailwind's JIT compiler keeps them.
 */
export const CATEGORY_PILL: Record<
  CampusEvent["category"],
  { highlight: string; text: string }
> = {
  club: {
    highlight: "bg-tag-blue/[0.18] ring-1 ring-inset ring-tag-blue/30",
    text: "text-tag-blue-ink",
  },
  academic: {
    highlight: "bg-tag-violet/[0.18] ring-1 ring-inset ring-tag-violet/30",
    text: "text-tag-violet-ink",
  },
  social: {
    highlight: "bg-tag-coral/[0.18] ring-1 ring-inset ring-tag-coral/30",
    text: "text-tag-coral-ink",
  },
  career: {
    highlight: "bg-ink/[0.08] ring-1 ring-inset ring-ink/20",
    text: "text-ink",
  },
  sports: {
    highlight: "bg-tag-cyan/[0.18] ring-1 ring-inset ring-tag-cyan/30",
    text: "text-tag-cyan-ink",
  },
  arts: {
    highlight: "bg-tag-magenta/[0.18] ring-1 ring-inset ring-tag-magenta/30",
    text: "text-tag-magenta-ink",
  },
  community: {
    highlight: "bg-tag-green/[0.18] ring-1 ring-inset ring-tag-green/30",
    text: "text-tag-green-ink",
  },
  free_food: {
    highlight: "bg-tag-amber/[0.18] ring-1 ring-inset ring-tag-amber/30",
    text: "text-tag-amber-ink",
  },
};

/** The Deadline tag: an urgency signal, not a category, in the coral hue. */
export const DEADLINE_PILL = CATEGORY_PILL.social;

// "All" has no category hue; it gets a neutral ink wash in the same shape.
export const ALL_PILL = {
  highlight: "bg-ink/[0.06] ring-1 ring-inset ring-ink/15",
  text: "text-ink",
};
