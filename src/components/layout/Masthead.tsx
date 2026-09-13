"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { SITE_NAV_LINKS, isNavLinkActive } from "@/lib/site-nav";

// Current page: ink with an underline (DESIGN.md's underline-from-active).
// The rest sit a step quieter so the marker reads at a glance.
const NAV_LINK_CLASS =
  "interactive-focus px-1 py-2 underline-offset-[6px] decoration-2 transition-colors";
const NAV_LINK_ACTIVE_CLASS = "text-ink underline";
const NAV_LINK_IDLE_CLASS = "text-ink/60 hover:text-ink";

const HIDE_THRESHOLD = 80;
const DELTA = 6;

type MastheadProps = {
  hideOnScroll?: boolean;
  position?: "sticky" | "static";
  variant?: "glass" | "solid";
  /**
   * Hide the inline nav links on desktop only. Used on /events where the
   * left rail owns site navigation; mobile still gets the inline links
   * because no rail exists below the lg breakpoint.
   */
  hideNavOnDesktop?: boolean;
};

export function Masthead({
  hideOnScroll = false,
  position = "sticky",
  variant = "glass",
  hideNavOnDesktop = false,
}: MastheadProps) {
  const pathname = usePathname();
  const [hidden, setHidden] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const lastY = useRef(0);
  const canHide = position === "sticky" && hideOnScroll;
  const surfaceClass =
    variant === "solid"
      ? "border-b border-ink/10 bg-canvas/95 backdrop-blur"
      : "bg-white/40 backdrop-blur-xl";
  const positionClass = position === "sticky" ? "sticky top-0" : "relative";

  useEffect(() => {
    if (!canHide) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sticky/static is an external layout input
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
        setIsOpen(false); // Close dropdown when scrolling away
      } else {
        setHidden(false);
      }
      lastY.current = y;
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [canHide]);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 768) {
        setIsOpen(false);
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

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
            highlander<span className="text-muted">/</span>hub
          </span>
        </Link>

        {/* Desktop Navigation */}
        <nav
          aria-label="Site"
          className={`hidden md:flex items-center gap-4 text-[13px] font-medium md:gap-5 md:text-sm ${
            hideNavOnDesktop ? "lg:hidden" : ""
          }`}
        >
          {SITE_NAV_LINKS.map((link) => {
            const active = isNavLinkActive(link.href, pathname);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={`${NAV_LINK_CLASS} ${active ? NAV_LINK_ACTIVE_CLASS : NAV_LINK_IDLE_CLASS}`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Mobile Dropdown Trigger */}
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          aria-expanded={isOpen}
          aria-label="Toggle navigation menu"
          className="md:hidden interactive-focus flex h-10 w-10 items-center justify-center rounded-lg text-ink hover:bg-ink/5 transition-colors"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="1.5"
            className="h-6 w-6"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
          </svg>
        </button>
      </div>

      {/* Collapsible Mobile Menu panel */}
      {isOpen && (
        <div className="md:hidden border-t border-ink/10 animate-field-reveal">
          <nav aria-label="Mobile Site" className="mx-auto max-w-7xl px-4 py-3 flex flex-col gap-1 sm:px-6">
            {SITE_NAV_LINKS.map((link) => {
              const active = isNavLinkActive(link.href, pathname);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setIsOpen(false)}
                  aria-current={active ? "page" : undefined}
                  className={`interactive-focus block rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    active ? "bg-surface text-ink" : "text-ink/60 hover:bg-surface hover:text-ink"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>
      )}
    </header>
  );
}
