"use client";

import { useEffect } from "react";
import { Footer } from "@/components/layout/Footer";
import { Masthead } from "@/components/layout/Masthead";

type RouteErrorVariant = "home" | "events" | "event" | "about" | "submit";

type RouteErrorPageProps = {
  error: Error & { digest?: string };
  reset: () => void;
  variant: RouteErrorVariant;
};

const copy: Record<
  RouteErrorVariant,
  {
    label: string;
    title: string;
    body: string;
  }
> = {
  home: {
    label: "Highlander Hub",
    title: "Something broke loading campus events.",
    body: "Try again, or come back in a minute if the event feed is still unavailable.",
  },
  events: {
    label: "Events",
    title: "Something broke loading events.",
    body: "Try again to reload the event feed and filters.",
  },
  event: {
    label: "Event",
    title: "Something broke loading this event.",
    body: "Try again to reload the event details, date, location, and links.",
  },
  about: {
    label: "About",
    title: "Something broke loading this page.",
    body: "Try again to reload the project details.",
  },
  submit: {
    label: "Submit",
    title: "Something broke loading the submission form.",
    body: "Try again to reload the form before sending your event.",
  },
};

export function RouteErrorPage({ error, reset, variant }: RouteErrorPageProps) {
  const content = copy[variant];

  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />

      <section className="border-b border-ink/10">
        <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6 md:py-24">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
            {content.label}
          </p>
          <h1 className="mt-4 font-display text-[34px] font-semibold leading-[1.05] tracking-[-0.03em] text-ink md:text-5xl">
            {content.title}
          </h1>
          <p aria-live="polite" className="mt-3 max-w-xl text-base text-ink/70">
            {content.body}
          </p>
          <button
            type="button"
            onClick={reset}
            className="interactive-focus mt-8 inline-flex min-h-12 items-center rounded-lg bg-ink px-5 py-3 text-sm font-medium text-white transition-opacity hover:opacity-85"
          >
            Try again
          </button>
        </div>
      </section>

      <Footer />
    </main>
  );
}
