"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

const NAV_LINKS = [
  { href: "/#features", label: "Features", internal: true },
  { href: "/events", label: "Events", internal: true },
  { href: "/about", label: "About", internal: true },
];

const HIDE_THRESHOLD = 80;
const DELTA = 6;

export function Masthead() {
  const [hidden, setHidden] = useState(false);
  const lastY = useRef(0);

  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY;
      const dy = y - lastY.current;
      if (Math.abs(dy) < DELTA) return;
      if (dy > 0 && y > HIDE_THRESHOLD) {
        setHidden(true);
      } else {
        setHidden(false);
      }
      lastY.current = y;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (hidden) {
      root.style.setProperty("--masthead-h", "0px");
    } else {
      root.style.removeProperty("--masthead-h");
    }
  }, [hidden]);

  return (
    <header
      className={`sticky top-0 z-30 border-b border-ink/10 bg-canvas/95 backdrop-blur transition-transform duration-200 ease-out ${
        hidden ? "-translate-y-full" : "translate-y-0"
      }`}
    >
      <div className="mx-auto flex h-12 max-w-7xl items-center justify-between gap-4 px-4 sm:h-14 sm:gap-6 sm:px-6">
        <Link href="/" className="interactive-focus flex items-baseline gap-2.5">
          <span className="font-display text-[18px] font-semibold tracking-[-0.04em] leading-none text-ink sm:text-[22px]">
            highlander<span className="text-muted">/</span>hub
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
          className="flex items-center gap-3 text-[13px] md:hidden"
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
