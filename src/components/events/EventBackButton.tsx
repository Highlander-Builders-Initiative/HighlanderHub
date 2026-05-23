"use client";

import { useRouter } from "next/navigation";
import { getSavedReturnPath } from "@/lib/events/feed-session";

export function EventBackButton() {
  const router = useRouter();
  const handleClick = () => {
    const savedPath = getSavedReturnPath();
    if (savedPath && window.history.length > 1) {
      router.back();
      return;
    }

    router.push(savedPath ?? "/events", { scroll: false });
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className="interactive-focus inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink"
    >
      <span aria-hidden>←</span> Back
    </button>
  );
}
