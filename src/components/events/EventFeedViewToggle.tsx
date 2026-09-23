"use client";

import type { ReactNode } from "react";
import { AnimatedBackground } from "@/components/core/animated-background";
import type { FeedView } from "./events-filters";

const VIEWS: { value: FeedView; label: string; icon: ReactNode }[] = [
  {
    value: "cards",
    label: "Cards",
    // Two stacked cards.
    icon: (
      <>
        <rect x="3" y="4" width="18" height="7" rx="2" />
        <rect x="3" y="13" width="18" height="7" rx="2" />
      </>
    ),
  },
  {
    value: "compact",
    label: "Compact",
    // A list: short rows, each with a lead mark.
    icon: <path d="M9 6h12M9 12h12M9 18h12M4 6h.01M4 12h.01M4 18h.01" />,
  },
];

type EventFeedViewToggleProps = {
  view: FeedView;
  onViewChange: (next: FeedView) => void;
  className?: string;
};

/**
 * Cards / Compact switch for the feed, in the feed header: two icons, named
 * for screen readers and on hover. The same trackless shape and neutral
 * selected fill as the When control (the one selected state, DESIGN.md).
 */
export function EventFeedViewToggle({
  view,
  onViewChange,
  className = "",
}: EventFeedViewToggleProps) {
  return (
    <div className={`flex ${className}`} role="group" aria-label="Feed view">
      <AnimatedBackground
        defaultValue={view}
        onValueChange={(id) => {
          if (id) onViewChange(id as FeedView);
        }}
        className="rounded-full bg-ink/[0.06]"
        transition={{ duration: 0 }}
      >
        {VIEWS.map((v) => {
          const active = view === v.value;
          return (
            <button
              key={v.value}
              data-id={v.value}
              type="button"
              aria-pressed={active}
              aria-label={v.label}
              title={v.label}
              className={`interactive-focus inline-flex h-8 w-10 items-center justify-center rounded-full transition-colors ${
                active ? "text-ink" : "text-muted hover:text-ink"
              }`}
            >
              <svg
                aria-hidden
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-4 w-4"
              >
                {v.icon}
              </svg>
            </button>
          );
        })}
      </AnimatedBackground>
    </div>
  );
}
