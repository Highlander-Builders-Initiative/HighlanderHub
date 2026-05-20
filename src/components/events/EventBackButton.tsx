"use client";

import { useRouter } from "next/navigation";
import { getSavedReturnPath } from "@/lib/scroll-restoration";

export function EventBackButton() {
  const router = useRouter();
  const handleClick = () => {
    router.push(getSavedReturnPath() ?? "/events", { scroll: false });
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
