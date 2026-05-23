"use client";

import { useRouter } from "next/navigation";

export function SubmitBackButton() {
  const router = useRouter();

  const handleBack = () => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
    } else {
      router.push("/events");
    }
  };

  return (
    <button
      type="button"
      onClick={handleBack}
      className="interactive-focus inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink transition-colors"
    >
      <span aria-hidden>←</span> Back
    </button>
  );
}
