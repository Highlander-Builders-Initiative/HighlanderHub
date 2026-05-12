export function Masthead() {
  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <header className="border-b-4 border-double border-ink">
      <div className="mx-auto max-w-7xl px-6 py-6">
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div className="font-mono text-[11px] uppercase tracking-widest">
            Vol. I · No. 01
          </div>
          <div className="font-mono text-[11px] uppercase tracking-widest">
            {today}
          </div>
          <div className="font-mono text-[11px] uppercase tracking-widest">
            Riverside, CA · 92521
          </div>
        </div>

        <h1 className="font-display text-[clamp(3rem,10vw,9rem)] leading-[0.85] tracking-tight text-center mt-4 mb-2 font-black">
          The Highlander
          <span className="italic font-light"> Daily</span>
        </h1>

        <div className="flex items-center justify-center gap-4 font-mono text-[11px] uppercase tracking-widest">
          <span className="h-px w-12 bg-ink" />
          <span>Campus & Club Events · UCR & Riverside</span>
          <span className="h-px w-12 bg-ink" />
        </div>
      </div>
    </header>
  );
}
