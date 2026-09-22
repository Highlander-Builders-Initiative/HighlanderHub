import { Fragment } from "react";
import { CATEGORY_PILL } from "@/lib/category-colors";
import type { EventCategory } from "@/types/event";

/** Hero category words, each in its category's tag text color. */
const HERO_HIGHLIGHTS: { label: string; category: EventCategory }[] = [
  { label: "Free food", category: "free_food" },
  { label: "club nights", category: "club" },
  { label: "intramurals", category: "sports" },
  { label: "art shows", category: "arts" },
  { label: "study groups", category: "academic" },
  { label: "career fairs", category: "career" },
];

export function HeroHighlightCopy() {
  return (
    <>
      {HERO_HIGHLIGHTS.map((item, index) => (
        <Fragment key={item.label}>
          {index > 0 ? ", " : null}
          <span className={`font-medium ${CATEGORY_PILL[item.category].text}`}>
            {item.label}
          </span>
        </Fragment>
      ))}
      . Everything happening on campus, pulled into one place you can actually
      scan.
    </>
  );
}
