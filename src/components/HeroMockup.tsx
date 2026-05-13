type MockEvent = {
  day: string;
  month: string;
  time: string;
  title: string;
  host: string;
  category: { label: string; cls: string };
  free?: boolean;
  rail: string;
};

const MOCK_EVENTS: MockEvent[] = [
  {
    day: "12",
    month: "MAY",
    time: "7:00 PM",
    title: "ACM General Meeting: Intro to System Design",
    host: "ACM at UCR",
    category: { label: "Club", cls: "bg-highlander/10 text-highlander" },
    rail: "bg-highlander",
  },
  {
    day: "13",
    month: "MAY",
    time: "12:30 PM",
    title: "Free Bagels at the HUB Lawn",
    host: "ASUCR",
    category: { label: "Free food", cls: "bg-gold/20 text-[#8a6300]" },
    free: true,
    rail: "bg-gold",
  },
  {
    day: "14",
    month: "MAY",
    time: "8:00 PM",
    title: "Open Mic Night at The Barn",
    host: "Programming Board",
    category: { label: "Arts", cls: "bg-coral/10 text-[#b33a30]" },
    rail: "bg-coral",
  },
];

export function HeroMockup() {
  return (
    <div className="relative" aria-hidden="true">
      {/* Background frame */}
      <div className="rounded-[18px] border border-ink/15 bg-canvas p-3 shadow-[0_30px_80px_-30px_rgba(15,17,21,0.25)]">
        {/* Faux browser chrome */}
        <div className="flex items-center justify-between px-2 pb-3 pt-1">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-ink/15" />
            <span className="h-2.5 w-2.5 rounded-full bg-ink/15" />
            <span className="h-2.5 w-2.5 rounded-full bg-ink/15" />
          </div>
          <div className="flex-1 mx-3 truncate rounded-md bg-ink/[0.04] px-3 py-1 font-mono text-[11px] text-muted">
            highlander.hub / events
          </div>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
            Preview
          </span>
        </div>

        {/* Inner panel */}
        <div className="rounded-[12px] border border-ink/10 bg-canvas">
          {/* Header inside */}
          <div className="flex items-baseline justify-between gap-3 border-b border-ink/10 px-4 py-3">
            <span className="font-display text-base font-semibold tracking-[-0.02em] text-ink">
              This week
            </span>
            <div className="flex items-end gap-4 text-xs">
              <span className="text-ink underline underline-offset-4 decoration-2 decoration-ink">
                List
              </span>
              <span className="text-muted">Calendar</span>
            </div>
          </div>

          {/* Chip row */}
          <div className="flex flex-wrap gap-1.5 border-b border-ink/10 px-4 py-3">
            {["All", "Clubs", "Free food", "Career", "Arts"].map((c, i) => (
              <span
                key={c}
                className={`inline-flex h-6 items-center border px-2 text-[11px] ${
                  i === 0
                    ? "border-ink bg-ink text-white"
                    : "border-ink/15 text-ink"
                }`}
              >
                {c}
              </span>
            ))}
          </div>

          {/* Event rows */}
          <ul className="divide-y divide-ink/10">
            {MOCK_EVENTS.map((ev, i) => (
              <li key={i} className="flex gap-3 px-4 py-3.5">
                <span className={`w-[3px] shrink-0 ${ev.rail}`} />
                <div className="flex flex-1 items-start gap-3">
                  <div className="flex flex-col items-baseline gap-0">
                    <span className="font-display text-xl font-semibold leading-none tracking-[-0.04em] text-ink">
                      {ev.day}
                    </span>
                    <span className="font-mono text-[10px] tracking-[0.16em] text-muted">
                      {ev.month}
                    </span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex flex-wrap items-center gap-1.5">
                      <span
                        className={`inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium ${ev.category.cls}`}
                      >
                        {ev.category.label}
                      </span>
                      {ev.free && (
                        <span className="inline-flex items-center bg-leaf/10 px-1.5 py-0.5 text-[10px] font-medium text-[#1f6f4e]">
                          Free
                        </span>
                      )}
                      <span className="ml-auto font-mono text-[10px] text-muted">
                        {ev.time}
                      </span>
                    </div>
                    <p className="truncate font-display text-[14px] font-semibold leading-snug tracking-[-0.01em] text-ink">
                      {ev.title}
                    </p>
                    <p className="truncate text-xs text-muted">{ev.host}</p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Floating accent badges */}
      <div className="pointer-events-none absolute -left-6 top-12 hidden rotate-[-4deg] items-center gap-2 border border-ink/15 bg-canvas px-3 py-1.5 shadow-[0_10px_30px_-12px_rgba(15,17,21,0.25)] md:flex">
        <span className="h-2 w-2 rounded-full bg-leaf" />
        <span className="text-xs font-medium text-ink">Live feed</span>
      </div>
      <div className="pointer-events-none absolute -right-4 bottom-10 hidden rotate-[3deg] items-center gap-2 border border-ink/15 bg-gold/15 px-3 py-1.5 shadow-[0_10px_30px_-12px_rgba(15,17,21,0.25)] md:flex">
        <span className="text-xs font-semibold text-[#8a6300]">
          Free bagels at 12:30
        </span>
      </div>
    </div>
  );
}
