"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

const NAV_LINKS = [
  { href: "/events", label: "Events", internal: true },
  { href: "/about", label: "About", internal: true },
];

const HIDE_THRESHOLD = 80;
const DELTA = 6;

type MastheadProps = {
  hideOnScroll?: boolean;
  position?: "sticky" | "static";
  variant?: "glass" | "solid";
};

export function Masthead({
  hideOnScroll = false,
  position = "sticky",
  variant = "glass",
}: MastheadProps) {
  const [hidden, setHidden] = useState(false);
  const lastY = useRef(0);
  const canHide = position === "sticky" && hideOnScroll;
  const surfaceClass =
    variant === "solid"
      ? "border-b border-ink/10 bg-canvas/95 backdrop-blur"
      : "bg-white/40 backdrop-blur-xl";
  const positionClass = position === "sticky" ? "sticky top-0" : "relative";

  useEffect(() => {
    if (!canHide) {
      setHidden(false);
      lastY.current = 0;
      return;
    }

    lastY.current = window.scrollY;

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
  }, [canHide]);

  useEffect(() => {
    const root = document.documentElement;
    if (canHide && hidden) {
      root.style.setProperty("--masthead-h", "0px");
    } else {
      root.style.removeProperty("--masthead-h");
    }
    return () => {
      root.style.removeProperty("--masthead-h");
    };
  }, [canHide, hidden]);

  return (
    <header
      className={`${positionClass} z-50 ${surfaceClass} transition-transform duration-200 ease-out ${
        hidden ? "-translate-y-full" : "translate-y-0"
      }`}
    >
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" className="interactive-focus flex items-baseline gap-2.5">
          <span className="font-display text-[18px] font-semibold tracking-[-0.04em] leading-none text-ink sm:text-[22px]">
            highlander<span className="text-black">/</span>hub
          </span>
        </Link>

        <nav
          aria-label="Sections"
          className="hidden items-center gap-5 text-sm font-medium md:flex"
        >
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="interactive-focus px-1 py-2 text-black transition-colors hover:text-ink/70"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <nav
          aria-label="Mobile navigation"
          className="flex items-center gap-4 text-[13px] font-medium md:hidden"
        >
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="interactive-focus px-1 py-2 text-black hover:text-ink/70"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
