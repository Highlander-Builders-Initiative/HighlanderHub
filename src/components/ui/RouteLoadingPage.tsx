import { Footer } from "@/components/layout/Footer";
import { Masthead } from "@/components/layout/Masthead";

type LoadingVariant = "home" | "events" | "event" | "about" | "submit";

const copy: Record<
  LoadingVariant,
  {
    label: string;
    title: string;
    body: string;
  }
> = {
  home: {
    label: "Highlander Hub",
    title: "Loading campus events",
    body: "Getting the latest UCR listings ready.",
  },
  events: {
    label: "Events",
    title: "Loading events",
    body: "Building the browseable event feed.",
  },
  event: {
    label: "Event",
    title: "Loading event details",
    body: "Fetching the date, host, location, and links.",
  },
  about: {
    label: "About",
    title: "Loading Highlander Hub",
    body: "Preparing the project details.",
  },
  submit: {
    label: "Submit",
    title: "Loading submission form",
    body: "Getting the event form ready.",
  },
};

function LoadingBars({ count = 4 }: { count?: number }) {
  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className="h-3 rounded-full bg-ink/10"
          style={{ width: `${92 - index * 13}%` }}
        />
      ))}
    </div>
  );
}

function LoadingCards() {
  return (
    <div className="grid gap-3 md:grid-cols-3" aria-hidden="true">
      {Array.from({ length: 3 }).map((_, index) => (
        <div
          key={index}
          className="min-h-32 rounded-xl border border-ink/15 bg-canvas p-5"
        >
          <div className="h-2 w-14 rounded-full bg-ink/10" />
          <div className="mt-5 h-4 w-3/4 rounded-full bg-ink/10" />
          <div className="mt-3 h-3 w-full rounded-full bg-ink/10" />
          <div className="mt-2 h-3 w-2/3 rounded-full bg-ink/10" />
        </div>
      ))}
    </div>
  );
}

export function RouteLoadingPage({
  variant,
}: {
  variant: LoadingVariant;
}) {
  const content = copy[variant];
  const isCompact = variant === "event" || variant === "submit";

  return (
    <main className="min-h-screen bg-canvas" aria-busy="true">
      <Masthead />

      <section className="border-b border-ink/10">
        <div
          className={`mx-auto px-4 sm:px-6 ${
            isCompact
              ? "max-w-3xl py-14 md:py-20"
              : "max-w-7xl py-16 md:py-24"
          }`}
        >
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
            {content.label}
          </p>
          <h1 className="mt-4 max-w-2xl font-display text-[34px] font-semibold leading-[1.05] tracking-[-0.03em] text-ink md:text-5xl">
            {content.title}
          </h1>
          <p className="mt-3 max-w-xl text-base text-ink/70">
            {content.body}
          </p>
        </div>
      </section>

      <section
        className={`mx-auto px-4 py-10 sm:px-6 ${
          isCompact ? "max-w-3xl" : "max-w-7xl"
        }`}
      >
        {variant === "events" ? (
          <div className="grid gap-6 md:grid-cols-[260px_1fr]">
            <aside className="rounded-xl border border-ink/15 bg-canvas p-5">
              <LoadingBars count={5} />
            </aside>
            <div className="space-y-4">
              <LoadingCards />
              <LoadingCards />
            </div>
          </div>
        ) : variant === "event" || variant === "submit" ? (
          <div className="rounded-xl border border-ink/15 bg-canvas p-6 sm:p-8">
            <LoadingBars count={6} />
          </div>
        ) : (
          <LoadingCards />
        )}
      </section>

      <Footer />
    </main>
  );
}
