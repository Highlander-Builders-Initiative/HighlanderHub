import { Fragment } from "react";
import Link from "next/link";
import { CATEGORY_PILL, FREE_FOOD_PILL } from "@/lib/category-colors";
import { eventsFeedHref } from "@/components/events/events-filters";

/** Hero words, each in its topic's tag text color. */
const HERO_HIGHLIGHTS: { label: string; href: string; text: string }[] = [
  { label: "Free food", href: eventsFeedHref({ freeFood: true }), text: FREE_FOOD_PILL.text },
  { label: "club nights", href: eventsFeedHref({ category: "hangout" }), text: CATEGORY_PILL.hangout.text },
  { label: "intramurals", href: eventsFeedHref({ category: "sports" }), text: CATEGORY_PILL.sports.text },
  { label: "art shows", href: eventsFeedHref({ category: "arts" }), text: CATEGORY_PILL.arts.text },
  { label: "study groups", href: eventsFeedHref({ category: "academic" }), text: CATEGORY_PILL.academic.text },
  { label: "career fairs", href: eventsFeedHref({ category: "career" }), text: CATEGORY_PILL.career.text },
];

/** Each word opens the feed filtered to its topic. The hairline underline
 *  marks them as links without leaning on color alone; it takes the word's
 *  color on hover. */
export function HeroHighlightCopy() {
  return (
    <>
      {HERO_HIGHLIGHTS.map((item, index) => (
        <Fragment key={item.label}>
          {index > 0 ? ", " : null}
          <Link
            href={item.href}
            className={`interactive-focus font-medium underline decoration-ink/20 decoration-1 underline-offset-[5px] transition-colors hover:decoration-current ${item.text}`}
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
