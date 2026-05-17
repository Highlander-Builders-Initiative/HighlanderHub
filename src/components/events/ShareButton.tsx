"use client";

import { useState } from "react";
import type { CampusEvent } from "@/types/event";
import { formatDay, formatTimeRange } from "@/lib/dates";
import { shareHref } from "@/lib/event-actions";

type Variant = "text" | "icon";

function buildPayload(event: CampusEvent) {
  const url =
    typeof window !== "undefined"
      ? window.location.href
      : `https://highlanderhub.app/events/${event.id}`;
  const text = [
    `${formatDay(event.startsAt)} · ${formatTimeRange(event.startsAt, event.endsAt)}`,
    event.location,
  ]
    .filter(Boolean)
    .join(" — ");
  return { title: event.title, text, url };
}

export function ShareButton({
  event,
  variant = "text",
}: {
  event: CampusEvent;
  variant?: Variant;
}) {
  const [state, setState] = useState<"idle" | "copied">("idle");

  async function handleShare() {
    const payload = buildPayload(event);

    if (typeof navigator !== "undefined" && typeof navigator.share === "function") {
      try {
        await navigator.share(payload);
        return;
      } catch (err) {
        // User canceled the share sheet — nothing to do.
        if (err instanceof DOMException && err.name === "AbortError") return;
        // Any other share failure: fall through to clipboard.
      }
    }

    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(payload.url);
        setState("copied");
        setTimeout(() => setState("idle"), 2000);
        return;
      } catch {
        // Fall through to mailto.
      }
    }

    window.location.href = shareHref(event);
  }

  if (variant === "icon") {
    return (
      <button
        type="button"
        onClick={handleShare}
        aria-label={state === "copied" ? "Link copied" : "Share"}
        className="interactive-focus inline-flex min-h-12 min-w-12 items-center justify-center rounded-lg border border-ink/15 text-ink"
      >
        {state === "copied" ? (
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
            <path d="M20 6 9 17l-5-5" />
          </svg>
        ) : (
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
            <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
            <path d="M16 6l-4-4-4 4" />
            <path d="M12 2v13" />
          </svg>
        )}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={handleShare}
      className="interactive-focus text-sm font-medium text-ink underline-offset-4 hover:underline"
    >
      {state === "copied" ? "Link copied" : "Share"}
    </button>
  );
}
