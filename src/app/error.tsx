"use client";

import { useEffect } from "react";

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
    <main className="mx-auto flex min-h-[60vh] max-w-xl flex-col items-start justify-center px-4 py-16 sm:px-6">
      <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
        Error
      </p>
      <h1 className="mt-2 font-display text-3xl font-semibold tracking-[-0.02em] text-ink">
        Something broke loading this page.
      </h1>
      <p className="mt-3 text-sm text-muted">
        {error.message || "Unknown error."}
      </p>
      <button
        type="button"
        onClick={reset}
        className="interactive-focus mt-6 inline-flex min-h-12 items-center rounded-lg bg-ink px-5 py-3 text-sm font-medium text-white transition-opacity hover:opacity-85"
      >
        Try again
      </button>
    </main>
  );
}
