import Link from "next/link";

const NAV_LINKS = [
  { href: "/#features", label: "Features", internal: true },
  { href: "/events", label: "Events", internal: true },
  { href: "/#about", label: "About", internal: true },
];

export function Masthead() {
  return (
    <header className="sticky top-0 z-30 border-b border-ink/10 bg-canvas/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-6 px-4 sm:px-6">
        <Link href="/" className="interactive-focus flex items-baseline gap-2.5">
          <span className="font-display text-[22px] font-semibold tracking-[-0.04em] leading-none text-ink">
            highlander<span className="text-muted">/</span>hub
          </span>
          <span className="hidden font-mono text-[10px] uppercase tracking-[0.18em] text-muted sm:inline">
            UCR · 92521
          </span>
        </Link>

        <nav
          aria-label="Sections"
          className="hidden items-center gap-7 text-sm md:flex"
        >
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="interactive-focus text-muted transition-colors hover:text-ink"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <nav
          aria-label="Mobile navigation"
          className="flex items-center gap-4 text-sm md:hidden"
        >
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="interactive-focus text-muted hover:text-ink"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
