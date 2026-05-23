import { Reveal } from "@/components/ui/Reveal";

// Three rows of free-food previews stand in for what a typical listings strip
// looks like in /events. Treats the panel as a campus-paper listings column,
// not a card-inside-a-card; the gold tint carries the category signal.
const FREE_FOOD_PREVIEW = [
  { when: "12:30 PM today", title: "Free bagels at the HUB" },
  { when: "Fri · 4:00 PM", title: "Pizza, ASUCR town hall" },
  { when: "Sat · 6:30 PM", title: "Boba night, Glasgow Hall" },
];

const FILTER_VISUAL = (
  <div className="flex h-full flex-col gap-2 p-5">
    <span className="text-xs text-muted">Filter</span>
    <div className="flex flex-wrap gap-1.5">
      {[
        { l: "All", active: undefined },
        {
          l: "Clubs",
          active: {
            border: "border-highlander/30",
            bg: "bg-highlander/12",
            text: "text-[#1d5fbf]",
          },
        },
        { l: "Career", active: undefined },
        {
          l: "Free food",
          active: {
            border: "border-gold/40",
            bg: "bg-gold/15",
            text: "text-[#8a6300]",
          },
        },
        { l: "Arts", active: undefined },
        { l: "Sports", active: undefined },
      ].map((c) => (
        <span
          key={c.l}
          className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs ${
            c.active
              ? `${c.active.border} ${c.active.bg} ${c.active.text} font-medium`
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
);

const CALENDAR_VISUAL = (() => {
  const dotsByDay: Record<number, string[]> = {
    2: ["bg-gold", "bg-leaf"],
    5: ["bg-sky", "bg-highlander"],
    7: ["bg-white", "bg-white/70"],
    8: ["bg-coral"],
    10: ["bg-highlander", "bg-gold"],
    14: ["bg-leaf", "bg-sky"],
    18: ["bg-gold", "bg-coral", "bg-leaf"],
  };
  return (
    <div className="grid grid-cols-7 gap-px bg-ink/10 p-5">
      {Array.from({ length: 21 }).map((_, i) => {
        const dots = dotsByDay[i];
        const today = i === 7;
        return (
          <div
            key={i}
            className={`flex aspect-square flex-col items-start gap-1 p-1.5 ${
              today ? "bg-ink text-white" : "bg-canvas"
            }`}
          >
            <span
              className={`text-[11px] font-medium ${
                today ? "text-white/70" : "text-muted"
              }`}
            >
              {String(i + 1).padStart(2, "0")}
            </span>
            {dots && (
              <div className="mt-auto flex gap-0.5">
                {dots.map((c, j) => (
                  <span key={j} className={`h-1.5 w-1.5 ${c}`} />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
})();

export function Features() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 md:py-28">
      <Reveal className="mb-10 max-w-2xl">
        <h2 className="font-display text-3xl font-semibold leading-tight tracking-[-0.03em] text-ink md:text-5xl">
          One feed for the whole campus.
        </h2>
      </Reveal>

      <div className="flex flex-col gap-5">
        {/* Prominent: the sharpest claim gets the editorial spotlight. */}
        <Reveal
          as="article"
          className="grid overflow-hidden rounded-xl border border-ink/15 bg-canvas md:grid-cols-12"
        >
          <div className="flex flex-col justify-center bg-gold/10 px-5 py-6 md:col-span-7 md:px-8 md:py-9">
            <span className="text-[13px] font-medium text-[#8a6300]">
              Free food this week
            </span>
            <ul className="mt-3 divide-y divide-ink/10">
              {FREE_FOOD_PREVIEW.map((row) => (
                <li
                  key={row.title}
                  className="flex items-center justify-between gap-3 py-3"
                >
                  <div className="min-w-0">
                    <p className="font-mono text-[11px] tracking-[0.04em] text-[#8a6300]">
                      {row.when}
                    </p>
                    <p className="mt-0.5 truncate font-display text-base font-semibold tracking-[-0.01em] text-ink md:text-lg">
                      {row.title}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-gold/20 px-2 py-0.5 text-[10px] font-medium text-[#8a6300]">
                    Free food
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="flex flex-col justify-center gap-3 border-t border-ink/10 p-6 md:col-span-5 md:border-l md:border-t-0 md:p-8">
            <h3 className="font-display text-2xl font-semibold tracking-[-0.02em] text-ink md:text-3xl">
              Never miss a free meal again.
            </h3>
            <p className="text-sm text-ink/70 md:text-base">
              Free-food tagging across every source. Flip the toggle and you
              only see things with snacks attached.
            </p>
          </div>
        </Reveal>

        {/* Compact: two supporting capabilities, varied in rhythm from the lead. */}
        <div className="grid gap-5 md:grid-cols-2">
          <Reveal
            delay={120}
            as="article"
            className="flex flex-col overflow-hidden rounded-xl border border-ink/15 bg-canvas"
          >
            <div className="h-40 border-b border-ink/10 bg-canvas">
              {FILTER_VISUAL}
            </div>
            <div className="flex flex-1 flex-col gap-2 p-5">
              <h3 className="font-display text-xl font-semibold tracking-[-0.02em] text-ink">
                Filter to what you actually care about.
              </h3>
              <p className="text-sm text-ink/70">
                Clubs, career, sports, arts, community. Stack them, mix them,
                search across hosts and tags.
              </p>
            </div>
          </Reveal>

          <Reveal
            delay={240}
            as="article"
            className="flex flex-col overflow-hidden rounded-xl border border-ink/15 bg-canvas"
          >
            <div className="h-40 border-b border-ink/10 bg-canvas">
              {CALENDAR_VISUAL}
            </div>
            <div className="flex flex-1 flex-col gap-2 p-5">
              <h3 className="font-display text-xl font-semibold tracking-[-0.02em] text-ink">
                See your week at a glance.
              </h3>
              <p className="text-sm text-ink/70">
                Toggle the calendar to scan a whole month. Each day shows
                colored dots for every category running.
              </p>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
