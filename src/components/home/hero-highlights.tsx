import { Fragment } from "react";
import Link from "next/link";
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

/** Each word opens the feed filtered to its category. The hairline underline
 *  marks them as links without leaning on color alone; it takes the word's
 *  color on hover. */
export function HeroHighlightCopy() {
  return (
    <>
      {HERO_HIGHLIGHTS.map((item, index) => (
        <Fragment key={item.label}>
          {index > 0 ? ", " : null}
          <Link
            href={`/events?cat=${item.category}`}
            className={`interactive-focus font-medium underline decoration-ink/20 decoration-1 underline-offset-[5px] transition-colors hover:decoration-current ${CATEGORY_PILL[item.category].text}`}
          >
            {item.label}
          </Link>
        </Fragment>
      ))}
      . Everything happening on campus, pulled into one place you can actually
      scan.
    </>
  );
}
