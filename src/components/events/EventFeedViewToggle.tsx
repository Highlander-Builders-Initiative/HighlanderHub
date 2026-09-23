"use client";

import { AnimatedBackground } from "@/components/core/animated-background";
import type { FeedView } from "./events-filters";

const VIEWS: { value: FeedView; label: string }[] = [
  { value: "cards", label: "Cards" },
  { value: "compact", label: "Compact" },
];

type EventFeedViewToggleProps = {
  view: FeedView;
  onViewChange: (next: FeedView) => void;
  className?: string;
};

/**
 * Cards / Compact switch for the desktop feed, in the feed header. The same
 * trackless shape and neutral selected fill as the When control (the one
 * selected state, DESIGN.md).
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
              className={`interactive-focus rounded-full px-3 py-1.5 text-[13px] font-medium transition-colors ${
                active ? "text-ink" : "text-muted hover:text-ink"
              }`}
            >
              {v.label}
            </button>
          );
        })}
      </AnimatedBackground>
    </div>
  );
}
