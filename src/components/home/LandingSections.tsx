import Link from "next/link";
import type { ReactNode } from "react";
import { Reveal } from "@/components/ui/Reveal";

type Feature = {
  number: string;
  title: string;
  body: string;
  visual: ReactNode;
};

const FEATURE_VISUALS = {
  filter: (
    <div className="flex h-full flex-col gap-2 p-5">
      <span className="text-xs text-muted">Filter</span>
      <div className="flex flex-wrap gap-1.5">
        {[
          { l: "All", on: false },
          { l: "Clubs", on: true },
          { l: "Career", on: false },
          { l: "Free food", on: true },
          { l: "Arts", on: false },
          { l: "Sports", on: false },
        ].map((c) => (
          <span
            key={c.l}
            className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs ${
              c.on
                ? "border-ink bg-ink text-white"
                : "border-ink/15 bg-canvas text-ink"
            }`}
          >
            {c.l}
          </span>
        ))}
      </div>
      <div className="mt-3 border-t border-ink/10 pt-3 text-xs text-muted">
        Showing 14 events
      </div>
    </div>
  ),

  food: (
    <div className="flex h-full items-center p-5">
      <div className="flex flex-1 flex-col gap-1 rounded-lg border border-ink/15 bg-canvas p-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
          12:30 PM today
        </span>
        <span className="font-display text-lg font-semibold tracking-[-0.02em] text-ink">
          Free Bagels at the HUB
        </span>
        <div className="mt-1 flex gap-1.5">
          <span className="rounded-full bg-gold/20 px-2 py-0.5 text-[10px] font-medium text-[#8a6300]">
            Free food
          </span>
          <span className="rounded-full bg-leaf/10 px-2 py-0.5 text-[10px] font-medium text-[#1f6f4e]">
            Free
          </span>
        </div>
      </div>
    </div>
  ),

  calendar: (
    <div className="grid grid-cols-7 gap-px bg-ink/10 p-5">
      {Array.from({ length: 21 }).map((_, i) => {
        const has = [2, 5, 8, 10, 14, 18].includes(i);
        const today = i === 7;
        return (
          <div
            key={i}
            className={`flex aspect-square flex-col items-start gap-1 p-1.5 ${
              today ? "bg-ink text-white" : "bg-canvas"
            }`}
          >
            <span
              className={`font-mono text-[10px] ${
                today ? "text-white/70" : "text-muted"
              }`}
            >
              {String(i + 1).padStart(2, "0")}
            </span>
            {has && (
              <div className="mt-auto flex gap-0.5">
                <span
                  className={`h-1.5 w-1.5 ${
                    today ? "bg-white" : "bg-highlander"
                  }`}
                />
                {i % 2 === 0 && (
                  <span
                    className={`h-1.5 w-1.5 ${
                      today ? "bg-white/70" : "bg-coral"
                    }`}
                  />
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  ),
};

const FEATURES: Feature[] = [
  {
    number: "01",
    title: "Filter to what you actually care about.",
    body: "Clubs, career, sports, arts, community, free food. Stack them, mix them, search across hosts and tags.",
    visual: FEATURE_VISUALS.filter,
  },
  {
    number: "02",
    title: "Never miss a free meal again.",
    body: "Free-food tagging across every source. Turn on the toggle and you only see things with snacks attached.",
    visual: FEATURE_VISUALS.food,
  },
  {
    number: "03",
    title: "See your week at a glance.",
    body: "Toggle the calendar view to scan a whole month. Each day shows colored dots for every category running that day.",
    visual: FEATURE_VISUALS.calendar,
  },
];

export function Features() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 md:py-28">
      <Reveal className="mb-12 max-w-2xl">
        <h2 className="font-display text-3xl font-semibold leading-tight tracking-[-0.03em] text-ink md:text-5xl">
          One feed for the whole campus.
        </h2>
        <p className="mt-4 text-base text-ink/75">
          Built for the way UCR actually finds out about events. Bring every
          source into one place and make it easy to scan.
        </p>
      </Reveal>

      <div className="grid gap-6 md:grid-cols-3">
        {FEATURES.map((f, i) => (
          <Reveal key={f.number} delay={i * 120} as="article" className="flex flex-col overflow-hidden rounded-xl border border-ink/15 bg-canvas">
            <div className="h-44 border-b border-ink/10 bg-canvas">
              {f.visual}
            </div>
            <div className="flex flex-1 flex-col gap-2 p-5">
              <span className="font-mono text-[11px] tracking-[0.14em] text-muted">
                {f.number}
              </span>
              <h3 className="font-display text-xl font-semibold tracking-[-0.02em] text-ink">
                {f.title}
              </h3>
              <p className="text-sm text-ink/70">{f.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

export function FinalCTA() {
  return (
    <section className="relative border-b border-ink/10 bg-highlander/[0.04]">
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 w-[3px] bg-highlander"
      />
      <div className="mx-auto flex max-w-7xl flex-col items-start gap-8 px-4 py-20 sm:px-6 md:flex-row md:items-end md:justify-between md:py-24">
        <Reveal className="max-w-xl">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
            Ready when you are
          </p>
          <h2 className="mt-3 font-display text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-ink md:text-6xl">
            Stop missing events.
          </h2>
          <p className="mt-4 max-w-md text-base text-ink/75">
            See what&rsquo;s on this week. Filter by club, category, or free
            food.
          </p>
        </Reveal>
        <Reveal delay={120} className="flex flex-wrap items-center gap-x-5 gap-y-3">
          <Link
            href="/events"
            className="interactive-focus inline-flex min-h-12 items-center rounded-lg bg-ink px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-85"
          >
            Browse events
          </Link>
          <Link
            href="/submit"
            className="interactive-focus inline-flex min-h-12 items-center text-sm font-medium text-ink underline underline-offset-4 decoration-ink/30 hover:decoration-ink"
          >
            Submit an event
          </Link>
          <Link
            href="/about"
            className="interactive-focus inline-flex min-h-12 items-center text-sm font-medium text-ink underline underline-offset-4 decoration-ink/30 hover:decoration-ink"
          >
            About the project
          </Link>
        </Reveal>
      </div>
    </section>
  );
}
