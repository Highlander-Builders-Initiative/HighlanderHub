"use client";

import { useEffect, useRef } from "react";
import type { CampusEvent } from "@/types/event";
import { FlyerTile } from "./FlyerTile";

// The wall scrolls slowly; this is the resting pace in pixels per second.
const SPEED_PX_PER_SEC = 32;
// Repeat the source set until it is at least this wide-feeling, so the loop
// never reveals an empty edge even when only a few events are scheduled.
const MIN_TILES = 12;
// Cap the distinct flyers so the hero stays a brief, scannable preview rather
// than a long tab sequence; the full set lives behind "Browse events".
const MAX_DISTINCT = 14;

/**
 * A continuously scrolling, full-bleed strip of upcoming event flyers: the
 * campus bulletin wall, alive. The strip is also a normal horizontal scroller,
 * so touch users can swipe it and keyboard users can tab through the tiles.
 * Auto-scroll pauses on hover and on focus, and is skipped entirely under
 * `prefers-reduced-motion` (the strip stays a plain manual scroller).
 */
export function FlyerMarquee({ events }: { events: CampusEvent[] }) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(false);

  // Image-first so the wall reads rich; image-less events backfill the tail.
  const pool = [
    ...events.filter((e) => e.imageUrl),
    ...events.filter((e) => !e.imageUrl),
  ].slice(0, MAX_DISTINCT);

  const base: CampusEvent[] = [];
  if (pool.length > 0) {
    while (base.length < MIN_TILES) base.push(...pool);
  }
  const baseCount = base.length;

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el || baseCount === 0) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    // The exact width of one set, measured from the first duplicate tile, so
    // the wrap is seamless regardless of gap rounding.
    let setWidth = 0;
    const measure = () => {
      const loopChild = el.children[baseCount] as HTMLElement | undefined;
      setWidth = loopChild ? loopChild.offsetLeft : 0;
    };
    measure();
    window.addEventListener("resize", measure);

    let rafId = 0;
    let last = 0;
    let stopped = false;
    let carry = 0;
    const tick = (now: number) => {
      // Stops a loop left behind by a prior effect run (React StrictMode
      // mounts the effect twice in development) so only one loop ever runs.
      if (stopped) return;
      if (last === 0) last = now;
      // Clamp dt so a backgrounded tab does not jump the strip on return.
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      if (!pausedRef.current && !reduceMotion.matches && setWidth > 0) {
        // scrollLeft quantizes to whole pixels, so only ever apply whole-pixel
        // steps and carry the sub-pixel remainder; otherwise a fractional step
        // rounds up every frame and the strip runs far faster than intended.
        const advance = SPEED_PX_PER_SEC * dt + carry;
        const step = Math.floor(advance);
        carry = advance - step;
        if (step > 0) {
          let next = el.scrollLeft + step;
          if (next >= setWidth) next -= setWidth;
          el.scrollLeft = next;
        }
      }
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);

    return () => {
      stopped = true;
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", measure);
    };
  }, [baseCount]);

  if (baseCount === 0) return null;

  const pause = () => {
    pausedRef.current = true;
  };
  const resume = () => {
    pausedRef.current = false;
  };

  // First set: real, focusable links. Second set: silent visual duplicates.
  const loop = [...base, ...base];

  return (
    <div
      ref={scrollerRef}
      onPointerEnter={pause}
      onPointerLeave={resume}
      onFocusCapture={pause}
      onBlurCapture={resume}
      className="flex gap-3 overflow-x-auto overflow-y-hidden py-3 [-ms-overflow-style:none] [scroll-padding-inline:1rem] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      {loop.map((event, i) => {
        const isDuplicate = i >= baseCount;
        return (
          <div
            key={`${event.id}-${i}`}
            className="w-[160px] shrink-0 sm:w-[200px] md:w-[244px]"
          >
            <FlyerTile
              event={event}
              size="medium"
              aspectClassName="aspect-[4/5]"
              decorative={isDuplicate}
            />
          </div>
        );
      })}
    </div>
  );
}
