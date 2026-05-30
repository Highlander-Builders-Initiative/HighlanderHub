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
 * Filter-pill tints. The category color becomes the pill's own surface (no
 * leading dot): a barely-there wash on hover, a firmer wash plus the matched
 * deep text and a hairline ring when active. Opacities are tuned per hue so the
 * desaturated ones (sage) read at the same weight as the punchy ones (coral).
 * Literal class strings so Tailwind's JIT compiler keeps them.
 */
export const CATEGORY_PILL: Record<
  CampusEvent["category"],
  { hover: string; active: string }
> = {
  club: {
    hover: "hover:bg-highlander/[0.07]",
    active: "bg-highlander/[0.12] text-highlander ring-1 ring-inset ring-highlander/25",
  },
  academic: {
    hover: "hover:bg-leaf/[0.08]",
    active: "bg-leaf/[0.13] text-deep-leaf ring-1 ring-inset ring-leaf/25",
  },
  social: {
    hover: "hover:bg-coral/[0.08]",
    active: "bg-coral/[0.13] text-deep-coral ring-1 ring-inset ring-coral/25",
  },
  career: {
    hover: "hover:bg-ink/[0.05]",
    active: "bg-ink/[0.08] text-ink ring-1 ring-inset ring-ink/20",
  },
  sports: {
    hover: "hover:bg-sky/[0.08]",
    active: "bg-sky/[0.13] text-deep-sky ring-1 ring-inset ring-sky/25",
  },
  arts: {
    hover: "hover:bg-plum/[0.08]",
    active: "bg-plum/[0.13] text-deep-plum ring-1 ring-inset ring-plum/25",
  },
  community: {
    hover: "hover:bg-sage/[0.12]",
    active: "bg-sage/[0.18] text-deep-sage ring-1 ring-inset ring-sage/30",
  },
  free_food: {
    hover: "hover:bg-gold/[0.10]",
    active: "bg-gold/[0.14] text-deep-gold ring-1 ring-inset ring-gold/25",
  },
};

// "All" has no category hue; it gets a neutral ink wash in the same shape.
export const ALL_PILL = {
  hover: "hover:bg-ink/[0.04]",
  active: "bg-ink/[0.06] text-ink ring-1 ring-inset ring-ink/15",
};
