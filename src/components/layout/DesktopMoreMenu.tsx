"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { HbiLink } from "@/components/analytics/HbiLink";
import { HBI_INSTAGRAM_URL } from "@/lib/hbi";

const rowClass =
  "interactive-focus flex min-h-9 w-full items-center justify-between gap-3 whitespace-nowrap rounded-xl px-3 text-left text-[14px] text-ink/80 hover:bg-ink/[0.04] hover:text-ink focus-visible:bg-ink/[0.04]";
const panelClass = "flex flex-col gap-1";

/** The page footer's links, from lg, for the /events feed (see its page). */
export function DesktopMoreMenu() {
  const [open, setOpen] = useState(false);
  const [socialsOpen, setSocialsOpen] = useState(false);
  const [footerInView, setFooterInView] = useState(false);
  const rootRef = useRef<HTMLElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const socialsRef = useRef<HTMLButtonElement>(null);

  function close() {
    setOpen(false);
    setSocialsOpen(false);
  }

  useEffect(() => {
    if (!open) return;
    const dismiss = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) close();
    };
    const desktop = window.matchMedia("(min-width: 1024px)");
    const onResize = () => { if (!desktop.matches) close(); };
    document.addEventListener("pointerdown", dismiss);
    desktop.addEventListener("change", onResize);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      desktop.removeEventListener("change", onResize);
    };
  }, [open]);

  // The page footer carries these same links, and its bottom row sits where
  // this button does, so the button steps aside once the footer is on screen:
  // at the end of the feed, or when a filter leaves only a few events. The
  // body's size is watched too, since a filter shortens the page without a
  // scroll.
  useEffect(() => {
    let frame = 0;
    const check = () => {
      frame = 0;
      const footer = document.querySelector("footer");
      const inView = !!footer && footer.getBoundingClientRect().top < window.innerHeight;
      setFooterInView(inView);
      if (inView) close();
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(check); };
    const resizes = new ResizeObserver(schedule);
    resizes.observe(document.body);
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    schedule();
    return () => {
      cancelAnimationFrame(frame);
      resizes.disconnect();
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
    };
  }, []);

  return (
    // Full-width and pointer-transparent, so the button lines up with the
    // page's max-w-7xl edge (the masthead's links, the right rail) rather
    // than the viewport's corner.
    <div
      className={`pointer-events-none fixed inset-x-0 bottom-0 z-40 hidden transition-[opacity,visibility] duration-200 ease-out lg:block ${
        footerInView ? "invisible opacity-0" : ""
      }`}
    >
      <div className="mx-auto flex max-w-7xl justify-end px-4 pb-4 sm:px-6">
        <nav
          ref={rootRef}
          aria-label="More"
          className="pointer-events-auto relative"
          onBlur={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget)) close();
          }}
          onKeyDown={(event) => {
            if (event.key !== "Escape") return;
            event.preventDefault();
            if (socialsOpen) {
              setSocialsOpen(false);
              socialsRef.current?.focus();
            } else {
              close();
              triggerRef.current?.focus();
            }
          }}
        >
          {/* Sized and colored like the masthead's links: a quiet site link,
              not a control louder than the page's own navigation. */}
          <button
            ref={triggerRef}
            type="button"
            aria-expanded={open}
            aria-controls="desktop-more-links"
            onClick={() => { if (open) close(); else setOpen(true); }}
            className={`interactive-focus flex min-h-11 items-center gap-2 px-1 text-sm font-medium transition-colors ${
              open ? "text-ink" : "text-ink/60 hover:text-ink"
            }`}
          >
            <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M4 6h16M4 12h16M4 18h16" />
            </svg>
            More
          </button>
          {open && (
            <div id="desktop-more-links" className={`absolute bottom-full right-0 mb-1 w-max ${panelClass}`}>
              <Link href="/about" className={rowClass} onClick={close}>About</Link>
              <div
                className="relative"
                onMouseEnter={() => setSocialsOpen(true)}
                onMouseLeave={() => {
                  if (!rootRef.current?.querySelector("#desktop-social-links")?.contains(document.activeElement)
                    && document.activeElement !== socialsRef.current) setSocialsOpen(false);
                }}
                onBlur={(event) => {
                  if (!event.currentTarget.contains(event.relatedTarget)) setSocialsOpen(false);
                }}
              >
                <button
                  ref={socialsRef}
                  type="button"
                  aria-expanded={socialsOpen}
                  aria-controls="desktop-social-links"
                  onClick={() => setSocialsOpen(true)}
                  className={`${rowClass} ${socialsOpen ? "bg-ink/[0.04] text-ink" : ""}`}
                >
                  Socials
                  <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className="text-muted">
                    <path d="m14 6-6 6 6 6" />
                  </svg>
                </button>
                {socialsOpen && (
                  // Centered on the Socials row, so the list opens around the
                  // row it came from (Discord level with Socials) instead of
                  // hanging down to the menu's foot.
                  <div id="desktop-social-links" className="absolute right-full top-1/2 w-max -translate-y-1/2 pr-1">
                    <div className={panelClass} onClick={close}>
                      <HbiLink href={HBI_INSTAGRAM_URL} location="more_menu" channel="instagram" className={rowClass}>Instagram</HbiLink>
                      <HbiLink href="https://discord.com/invite/QYCQwTTvfS" location="more_menu" channel="discord" className={rowClass}>Discord</HbiLink>
                      <HbiLink href="https://www.linkedin.com/company/hbi/" location="more_menu" channel="linkedin" className={rowClass}>LinkedIn</HbiLink>
                    </div>
                  </div>
                )}
              </div>
              <Link href="/privacy" className={rowClass} onClick={close}>Privacy Policy</Link>
              <Link href="/terms" className={rowClass} onClick={close}>Terms of Service</Link>
            </div>
          )}
        </nav>
      </div>
    </div>
  );
}
