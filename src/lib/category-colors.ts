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

/**
 * Filter-pill colors. `highlight` tints the sliding selection background (a
 * soft category wash plus a matched hairline ring); `text` is the matched deep
 * text for the selected row. Opacities are tuned per hue so the desaturated
 * ones (sage) read at the same weight as the punchy ones (coral). Literal class
 * strings so Tailwind's JIT compiler keeps them.
 */
export const CATEGORY_PILL: Record<
  CampusEvent["category"],
  { highlight: string; text: string }
> = {
  club: {
    highlight: "bg-highlander/[0.12] ring-1 ring-inset ring-highlander/25",
    text: "text-highlander",
  },
  academic: {
    highlight: "bg-leaf/[0.13] ring-1 ring-inset ring-leaf/25",
    text: "text-deep-leaf",
  },
  social: {
    highlight: "bg-coral/[0.13] ring-1 ring-inset ring-coral/25",
    text: "text-deep-coral",
  },
  career: {
    highlight: "bg-ink/[0.08] ring-1 ring-inset ring-ink/20",
    text: "text-ink",
  },
  sports: {
    highlight: "bg-sky/[0.13] ring-1 ring-inset ring-sky/25",
    text: "text-deep-sky",
  },
  arts: {
    highlight: "bg-plum/[0.13] ring-1 ring-inset ring-plum/25",
    text: "text-deep-plum",
  },
  community: {
    highlight: "bg-sage/[0.18] ring-1 ring-inset ring-sage/30",
    text: "text-deep-sage",
  },
  free_food: {
    highlight: "bg-gold/[0.14] ring-1 ring-inset ring-gold/25",
    text: "text-deep-gold",
  },
};

// "All" has no category hue; it gets a neutral ink wash in the same shape.
export const ALL_PILL = {
  highlight: "bg-ink/[0.06] ring-1 ring-inset ring-ink/15",
  text: "text-ink",
};
