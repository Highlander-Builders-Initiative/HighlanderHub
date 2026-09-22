"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { SITE_NAV_LINKS, isNavLinkActive } from "@/lib/site-nav";

// Current page: ink with an underline (DESIGN.md's underline-from-active).
// The rest sit a step quieter so the marker reads at a glance. Links sit inline
// at every width (no menu button), each a 44px-tall touch target.
const NAV_LINK_CLASS =
  "interactive-focus inline-flex min-h-11 items-center px-1 underline-offset-[6px] decoration-2 transition-colors";
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
            highlander<span className="text-muted">/</span>hub
          </span>
        </Link>

        <nav
          aria-label="Site"
          className={`flex items-center gap-4 text-[13px] font-medium md:gap-5 md:text-sm ${
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
      </div>
    </header>
  );
}
