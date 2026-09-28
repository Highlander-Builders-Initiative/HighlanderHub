import { type CampusEvent, categoryShortLabel } from "@/types/event";
import { isDeadlineKind } from "@/lib/events/content-kind";

// The palette moved over with the categories: Hang out keeps Social's coral,
// Get involved Club's blue, Volunteering Community's green. `other` names no
// activity, so it has no hue.
export const CATEGORY_RAIL: Record<CampusEvent["category"], string> = {
  hangout: "bg-tag-coral",
  get_involved: "bg-tag-blue",
  career: "bg-ink",
  academic: "bg-tag-violet",
  sports: "bg-tag-cyan",
  arts: "bg-tag-magenta",
  volunteering: "bg-tag-green",
  other: "bg-ink/30",
};

/**
 * Tag and filter-pill colors. `highlight` is the pill background (a bright
 * category wash plus a matched hairline ring; the Topics rail uses it for
 * the selected row); `text` is the matched ink. Literal class
 * strings so Tailwind's JIT compiler keeps them.
 */
export const CATEGORY_PILL: Record<
  CampusEvent["category"],
  { highlight: string; text: string }
> = {
  hangout: {
    highlight: "bg-tag-coral/[0.18] ring-1 ring-inset ring-tag-coral/30",
    text: "text-tag-coral-ink",
  },
  get_involved: {
    highlight: "bg-tag-blue/[0.18] ring-1 ring-inset ring-tag-blue/30",
    text: "text-tag-blue-ink",
  },
  career: {
    highlight: "bg-ink/[0.08] ring-1 ring-inset ring-ink/20",
    text: "text-ink",
  },
  academic: {
    highlight: "bg-tag-violet/[0.18] ring-1 ring-inset ring-tag-violet/30",
    text: "text-tag-violet-ink",
  },
  sports: {
    highlight: "bg-tag-cyan/[0.18] ring-1 ring-inset ring-tag-cyan/30",
    text: "text-tag-cyan-ink",
  },
  arts: {
    highlight: "bg-tag-magenta/[0.18] ring-1 ring-inset ring-tag-magenta/30",
    text: "text-tag-magenta-ink",
  },
  volunteering: {
    highlight: "bg-tag-green/[0.18] ring-1 ring-inset ring-tag-green/30",
    text: "text-tag-green-ink",
  },
  other: {
    highlight: "bg-ink/[0.06]",
    text: "text-ink",
  },
};

/** Free food: an attribute of any event, in the amber hue. */
export const FREE_FOOD_PILL = {
  highlight: "bg-tag-amber/[0.18] ring-1 ring-inset ring-tag-amber/30",
  text: "text-tag-amber-ink",
};

/** The Deadline tag: an urgency signal, not a category, in the coral hue. */
export const DEADLINE_PILL = {
  highlight: "bg-tag-coral/[0.18] ring-1 ring-inset ring-tag-coral/30",
  text: "text-tag-coral-ink",
};

/** Unfilled: a note about attending, not a kind of event. */
const RSVP_PILL = {
  highlight: "ring-1 ring-inset ring-ink/15",
  text: "text-ink/70",
};

export type EventTag = {
  kind: "deadline" | "category" | "free_food" | "rsvp";
  label: string;
  highlight: string;
  text: string;
};

/**
 * The tag row on the feed card and the detail header, in order: Deadline, the
 * category, Free food, RSVP. An uncategorized event has no category tag.
 */
export function eventTags(
  event: Pick<CampusEvent, "contentKind" | "category" | "hasFreeFood" | "rsvpRequired">
): EventTag[] {
  const tags: EventTag[] = [];
  if (isDeadlineKind(event.contentKind)) {
    tags.push({ kind: "deadline", label: "Deadline", ...DEADLINE_PILL });
  }
  if (event.category !== "other") {
    tags.push({
      kind: "category",
      label: categoryShortLabel(event.category),
      ...CATEGORY_PILL[event.category],
    });
  }
  if (event.hasFreeFood) {
    tags.push({ kind: "free_food", label: "Free food", ...FREE_FOOD_PILL });
  }
  if (event.rsvpRequired) {
    tags.push({ kind: "rsvp", label: "RSVP", ...RSVP_PILL });
  }
  return tags;
}
