const NAV_LINKS = [
  { href: "#events", label: "Events" },
  { href: "#sources", label: "Sources" },
  { href: "#about", label: "About" },
];

export function Masthead() {
  return (
    <header className="sticky top-0 z-30 bg-canvas/85 backdrop-blur border-b border-line">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <a href="/" className="interactive-focus flex min-h-11 items-center gap-2.5 rounded-lg">
          <span
            aria-hidden
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-highlander text-white font-display font-bold"
          >
            H
          </span>
          <span className="font-display text-lg font-semibold">
            Highlander Hub
          </span>
        </a>

        <nav className="hidden md:flex items-center gap-7 text-sm text-muted">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="interactive-focus inline-flex min-h-11 items-center rounded-lg transition-colors hover:text-ink"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <a
          href="#events"
          className="interactive-focus inline-flex min-h-11 items-center gap-1.5 rounded-full bg-ink px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-highlander"
        >
          Browse events
          <span aria-hidden>→</span>
        </a>
      </div>
      <nav
        aria-label="Mobile section navigation"
        className="md:hidden border-t border-line"
      >
        <div className="mx-auto flex max-w-7xl items-center gap-2 overflow-x-auto px-4 py-2 sm:px-6">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="interactive-focus inline-flex min-h-11 shrink-0 items-center rounded-full border border-line px-4 text-sm font-medium text-ink transition-colors hover:border-highlander hover:text-highlander"
            >
              {link.label}
            </a>
          ))}
        </div>
      </nav>
    </header>
  );
}
