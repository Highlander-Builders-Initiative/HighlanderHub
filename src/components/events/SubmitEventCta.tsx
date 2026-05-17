"use client";

import Link from "next/link";
import { track } from "@/lib/analytics";

type Variant = "button" | "link";
type Surface = "events_header" | "empty_state";

export function SubmitEventCta({
  variant = "button",
  surface,
  className,
}: {
  variant?: Variant;
  surface: Surface;
  className?: string;
}) {
  const onClick = () => track("submit_cta_click", { surface });

  if (variant === "link") {
    return (
      <Link
        href="/submit"
        onClick={onClick}
        className={
          className ??
          "interactive-focus text-sm font-medium text-ink underline-offset-4 hover:underline"
        }
      >
        submit your own event →
      </Link>
    );
  }

  return (
    <Link
      href="/submit"
      onClick={onClick}
      className={
        className ??
        "interactive-focus group inline-flex min-h-12 items-center gap-2 rounded-lg border border-ink bg-canvas px-5 py-3 text-sm font-medium text-ink transition-colors hover:bg-ink hover:text-white"
      }
    >
      <svg
        aria-hidden
        viewBox="0 0 20 20"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="h-4 w-4"
      >
        <path d="M10 4v12M4 10h12" />
      </svg>
      Submit an event
    </Link>
  );
}
