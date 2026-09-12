"use client";

import { useEffect } from "react";
import {
  EVENT_MODAL_CONTAINER_CLASS,
  EVENT_MODAL_TITLE_ID,
} from "@/components/events/EventDetailView";

/** Renders inside the overlay shell, so the close controls stay available. */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className={EVENT_MODAL_CONTAINER_CLASS} aria-live="polite">
      <h2
        id={EVENT_MODAL_TITLE_ID}
        className="pr-12 font-display text-[24px] font-semibold tracking-[-0.02em] text-ink"
      >
        Something broke loading this event.
      </h2>
      <p className="mt-3 text-[15px] text-ink/75">
        Try again to reload the event details, date, location, and links.
      </p>
      <button
        type="button"
        onClick={reset}
        className="interactive-focus mt-6 inline-flex min-h-11 items-center rounded-lg bg-ink px-5 py-2 text-sm font-medium text-white transition-opacity hover:opacity-85"
      >
        Try again
      </button>
    </div>
  );
}
