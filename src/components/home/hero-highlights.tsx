import { Fragment } from "react";

/** Hero category chips — deep tokens for AA text on canvas (see tailwind accent comments). */
const HERO_HIGHLIGHTS = [
  { label: "Free food", className: "text-deep-gold" },
  { label: "club nights", className: "text-highlander" },
  { label: "intramurals", className: "text-deep-sky" },
  { label: "art shows", className: "text-deep-coral" },
  { label: "study groups", className: "text-deep-leaf" },
  { label: "career fairs", className: "text-ink" },
] as const;

export function HeroHighlightCopy() {
  return (
    <>
      {HERO_HIGHLIGHTS.map((item, index) => (
        <Fragment key={item.label}>
          {index > 0 ? ", " : null}
          <span className={`font-medium ${item.className}`}>{item.label}</span>
        </Fragment>
      ))}
      . Everything happening on campus, pulled into one place you can actually
      scan.
    </>
  );
}
