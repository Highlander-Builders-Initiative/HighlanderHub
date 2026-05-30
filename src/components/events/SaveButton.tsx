"use client";

import type { MouseEvent } from "react";
import { cn } from "@/lib/utils";
import { track } from "@/lib/analytics";
import { useSavedEvents } from "./useSavedEvents";

type Variant = "icon" | "label" | "card";
type Surface = "list_card" | "detail" | "saved_page";

type SaveButtonProps = {
  eventId: string;
  surface: Surface;
  variant?: Variant;
  className?: string;
};

/**
 * Heart toggle backed by localStorage (no account). Calls preventDefault +
 * stopPropagation so it can sit safely over a clickable card without
 * triggering navigation.
 */
export function SaveButton({
  eventId,
  surface,
  variant = "icon",
  className,
}: SaveButtonProps) {
  const { savedIds, toggle } = useSavedEvents();
  const saved = savedIds.includes(eventId);

  const handleClick = (clickEvent: MouseEvent<HTMLButtonElement>) => {
    clickEvent.preventDefault();
    clickEvent.stopPropagation();
    toggle(eventId);
    track("event_save", {
      id: eventId,
      action: saved ? "unsave" : "save",
      surface,
    });
  };

  const heart = (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill={saved ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
    >
      <path d="M20.8 5.6a5 5 0 0 0-7.1 0L12 7.3l-1.7-1.7a5 5 0 0 0-7.1 7.1l1.7 1.7L12 21.5l7.1-7.1 1.7-1.7a5 5 0 0 0 0-7.1Z" />
    </svg>
  );

  if (variant === "label") {
    return (
      <button
        type="button"
        onClick={handleClick}
        aria-pressed={saved}
        className={cn(
          "interactive-focus inline-flex items-center gap-1.5 text-sm font-medium underline-offset-4 hover:underline",
          saved ? "text-coral" : "text-ink",
          className
        )}
      >
        {heart}
        {saved ? "Saved" : "Save"}
      </button>
    );
  }

  if (variant === "card") {
    return (
      <button
        type="button"
        onClick={handleClick}
        aria-pressed={saved}
        aria-label={saved ? "Remove from saved" : "Save event"}
        className={cn(
          "interactive-focus inline-flex h-9 w-9 items-center justify-center rounded-full bg-canvas/85 shadow-sm backdrop-blur transition-colors",
          saved ? "text-coral" : "text-ink/45 hover:text-coral",
          className
        )}
      >
        {heart}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-pressed={saved}
      aria-label={saved ? "Remove from saved" : "Save event"}
      className={cn(
        "interactive-focus inline-flex min-h-12 min-w-12 items-center justify-center rounded-lg border border-ink/15",
        saved ? "text-coral" : "text-ink",
        className
      )}
    >
      {heart}
    </button>
  );
}
