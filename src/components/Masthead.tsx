export function Masthead() {
  return (
    <header className="sticky top-0 z-30 bg-canvas/85 backdrop-blur border-b border-line">
      <div className="mx-auto max-w-7xl px-6 h-16 flex items-center justify-between">
        <a href="/" className="flex items-center gap-2.5">
          <span
            aria-hidden
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-highlander text-white font-display font-bold"
          >
            H
          </span>
          <span className="font-display text-lg font-semibold tracking-tight">
            Highlander Hub
          </span>
        </a>

        <nav className="hidden md:flex items-center gap-7 text-sm text-muted">
          <a href="#events" className="hover:text-ink transition-colors">
            Events
          </a>
          <a href="#sources" className="hover:text-ink transition-colors">
            Sources
          </a>
          <a href="#about" className="hover:text-ink transition-colors">
            About
          </a>
        </nav>

        <a
          href="#events"
          className="inline-flex items-center gap-1.5 rounded-full bg-ink text-white px-4 py-2 text-sm font-medium hover:bg-highlander transition-colors"
        >
          Browse events
          <span aria-hidden>→</span>
        </a>
      </div>
    </header>
  );
}
