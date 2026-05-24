"use client";

import {
  motion,
  useAnimationFrame,
  useMotionValue,
  useReducedMotion,
} from "motion/react";
import { useEffect, useRef, useState } from "react";
import type { CampusEvent } from "@/types/event";
import { FlyerTile } from "./FlyerTile";

// The wall scrolls slowly; this is the resting pace in pixels per second.
const SPEED_PX_PER_SEC = 32;
const TILE_GAP_PX = 12;
const DRAG_CLICK_THRESHOLD_PX = 6;
const WHEEL_RESUME_DELAY_MS = 180;
// Repeat the source set until it is at least this wide-feeling, so the loop
// never reveals an empty edge even when only a few events are scheduled.
const MIN_TILES = 12;
// Cap the distinct flyers so the hero stays a brief, scannable preview rather
// than a long tab sequence; the full set lives behind "Browse events".
const MAX_DISTINCT = 14;

/**
 * A continuously scrolling, full-bleed strip of upcoming event flyers: the
 * campus bulletin wall, alive. The strip can also be dragged horizontally,
 * so touch users can swipe it and keyboard users can tab through the tiles.
 * Auto-scroll pauses on hover and on focus, and is skipped entirely under
 * `prefers-reduced-motion` (the strip stays a manual draggable strip).
 */
export function FlyerMarquee({ events }: { events: CampusEvent[] }) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const setRef = useRef<HTMLDivElement>(null);
  const setWidthRef = useRef(0);
  const pausedRef = useRef(false);
  const hoverPausedRef = useRef(false);
  const focusPausedRef = useRef(false);
  const dragPausedRef = useRef(false);
  const wheelPausedRef = useRef(false);
  const wheelResumeRef = useRef<number | null>(null);
  const dragDistanceRef = useRef(0);
  const lastDragAtRef = useRef(0);
  const [setWidth, setSetWidth] = useState(0);
  const x = useMotionValue(0);
  const shouldReduceMotion = useReducedMotion();

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
    const el = setRef.current;
    if (!el || baseCount === 0) return;

    const measure = () => {
      setSetWidth(el.getBoundingClientRect().width + TILE_GAP_PX);
    };
    measure();

    const observer = new ResizeObserver(measure);
    observer.observe(el);

    return () => {
      observer.disconnect();
    };
  }, [baseCount]);

  useEffect(() => {
    return () => {
      if (wheelResumeRef.current !== null) {
        window.clearTimeout(wheelResumeRef.current);
      }
    };
  }, []);

  useEffect(() => {
    setWidthRef.current = setWidth;
    x.set(wrapX(x.get(), setWidth));
  }, [setWidth, x]);

  useAnimationFrame((_, delta) => {
    const width = setWidthRef.current;
    if (pausedRef.current || shouldReduceMotion || width <= 0) return;

    const dt = Math.min(delta / 1000, 0.05);
    x.set(wrapX(x.get() - SPEED_PX_PER_SEC * dt, width));
  });

  if (baseCount === 0) return null;

  const updatePaused = () => {
    pausedRef.current =
      hoverPausedRef.current ||
      focusPausedRef.current ||
      dragPausedRef.current ||
      wheelPausedRef.current;
  };

  const setHoverPaused = (paused: boolean) => {
    hoverPausedRef.current = paused;
    updatePaused();
  };
  const setFocusPaused = (paused: boolean) => {
    focusPausedRef.current = paused;
    updatePaused();
  };
  const setDragPaused = (paused: boolean) => {
    dragPausedRef.current = paused;
    updatePaused();
  };
  const setWheelPaused = (paused: boolean) => {
    wheelPausedRef.current = paused;
    updatePaused();
  };
  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    const width = setWidthRef.current;
    if (width <= 0) return;

    const delta = event.deltaX !== 0 ? event.deltaX : event.shiftKey ? event.deltaY : 0;
    if (delta === 0) return;

    event.preventDefault();
    setWheelPaused(true);
    x.set(wrapX(x.get() - delta, width));

    if (wheelResumeRef.current !== null) {
      window.clearTimeout(wheelResumeRef.current);
    }
    wheelResumeRef.current = window.setTimeout(() => {
      setWheelPaused(false);
      wheelResumeRef.current = null;
    }, WHEEL_RESUME_DELAY_MS);
  };
  const focusTile = (target: EventTarget | null) => {
    if (!(target instanceof HTMLElement)) return;

    const tile = target.closest<HTMLElement>("[data-marquee-tile]");
    const viewport = viewportRef.current;
    if (!tile || !viewport) return;

    const tileStart = tile.offsetLeft;
    const tileEnd = tileStart + tile.offsetWidth;
    const viewportWidth = viewport.clientWidth;
    const currentX = x.get();
    const visibleStart = -currentX;
    const visibleEnd = visibleStart + viewportWidth;

    if (tileStart < visibleStart) {
      x.set(-tileStart);
    } else if (tileEnd > visibleEnd) {
      x.set(Math.min(0, viewportWidth - tileEnd));
    }
  };

  // First set: real, focusable links. Second set: silent visual duplicates.
  return (
    <div
      ref={viewportRef}
      onPointerEnter={() => setHoverPaused(true)}
      onPointerLeave={() => setHoverPaused(false)}
      onFocusCapture={(event) => {
        setFocusPaused(true);
        focusTile(event.target);
      }}
      onBlurCapture={() => setFocusPaused(false)}
      onWheel={handleWheel}
      className="overflow-hidden py-3"
    >
      <motion.div
        data-marquee-track=""
        data-marquee-width={setWidth}
        drag="x"
        dragMomentum={false}
        onDragStart={() => {
          dragDistanceRef.current = 0;
          setDragPaused(true);
        }}
        onDrag={(_, info) => {
          dragDistanceRef.current = Math.max(
            dragDistanceRef.current,
            Math.abs(info.offset.x)
          );
          x.set(wrapX(x.get(), setWidthRef.current));
        }}
        onDragEnd={() => {
          if (dragDistanceRef.current > DRAG_CLICK_THRESHOLD_PX) {
            lastDragAtRef.current = performance.now();
          }
          setDragPaused(false);
          x.set(wrapX(x.get(), setWidthRef.current));
        }}
        onClickCapture={(event) => {
          if (performance.now() - lastDragAtRef.current < 250) {
            event.preventDefault();
            event.stopPropagation();
          }
        }}
        style={{ x, gap: TILE_GAP_PX }}
        className="flex w-max cursor-grab active:cursor-grabbing"
      >
        <FlyerTileSet events={base} setRef={setRef} />
        <FlyerTileSet events={base} decorative />
      </motion.div>
    </div>
  );
}

function FlyerTileSet({
  events,
  decorative = false,
  setRef,
}: {
  events: CampusEvent[];
  decorative?: boolean;
  setRef?: React.Ref<HTMLDivElement>;
}) {
  return (
    <div ref={setRef} className="flex shrink-0" style={{ gap: TILE_GAP_PX }}>
      {events.map((event, i) => (
        <div
          key={`${event.id}-${decorative ? "duplicate" : "real"}-${i}`}
          data-marquee-tile=""
          className="w-[160px] shrink-0 sm:w-[200px] md:w-[244px]"
        >
          <FlyerTile
            event={event}
            size="medium"
            aspectClassName="aspect-[4/5]"
            decorative={decorative}
          />
        </div>
      ))}
    </div>
  );
}

function wrapX(value: number, width: number) {
  if (width <= 0) return 0;

  const wrapped = value % width;
  return wrapped > 0 ? wrapped - width : wrapped;
}
