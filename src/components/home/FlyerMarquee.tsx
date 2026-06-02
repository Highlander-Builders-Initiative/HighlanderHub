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
// Hover lets the strip keep breathing without snapping to a stop, so the
// spotlight effect stays legible without forcing the eye to chase tiles.
const HOVER_SPEED_FACTOR = 0.3;
const TILE_GAP_PX = 20;
const DRAG_CLICK_THRESHOLD_PX = 6;
const WHEEL_RESUME_DELAY_MS = 180;
// Spotlight falloff: tiles within this distance of the focal point earn
// a non-zero focal value; past it they sit flat.
const FOCAL_RADIUS_PX = 240;
// Frame-rate-independent glide rates for focal X and speed. Higher =
// snappier toward target.
const FOCAL_LERP_PER_SEC = 9;
const SPEED_LERP_PER_SEC = 5;
// Repeat the source set until it is at least this wide-feeling, so the loop
// never reveals an empty edge even when only a few events are scheduled.
const MIN_TILES = 12;
// Cap the distinct flyers so the hero stays a brief, scannable preview rather
// than a long tab sequence; the full set lives behind "Browse events".
const MAX_DISTINCT = 14;

/**
 * A continuously scrolling, full-bleed strip of upcoming event flyers: the
 * campus bulletin wall, alive. Tiles within a focal radius (viewport center
 * at rest, pointer-x while hovering) lift and gain a soft drop shadow, so
 * the eye is always quietly guided to the center of the strip. The track
 * can also be dragged horizontally for touch and tabbed for keyboard.
 * Auto-scroll slows on hover, fully pauses on focus / drag / wheel, and is
 * skipped entirely under `prefers-reduced-motion`.
 */
export function FlyerMarquee({ events }: { events: CampusEvent[] }) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const setRef = useRef<HTMLDivElement>(null);
  // Pre-measured tile centers within the track; refreshed on resize so the
  // rAF loop avoids per-frame layout reads.
  const tileGeomRef = useRef<{ el: HTMLElement; centerInTrack: number }[]>([]);
  const setWidthRef = useRef(0);
  const pausedRef = useRef(false);
  const focusPausedRef = useRef(false);
  const dragPausedRef = useRef(false);
  const wheelPausedRef = useRef(false);
  const wheelResumeRef = useRef<number | null>(null);
  const dragDistanceRef = useRef(0);
  const lastDragAtRef = useRef(0);
  const hoveringRef = useRef(false);
  // Negative sentinel = not yet initialised (no layout measured).
  const focalRef = useRef(-1);
  const focalTargetRef = useRef(-1);
  const speedRef = useRef(1);
  const speedTargetRef = useRef(1);
  // Spotlight intensity. Only the hover/focus pointer earns a focal
  // lift — at rest the row reads flat and consistent.
  const intensityRef = useRef(0);
  const intensityTargetRef = useRef(0);
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

  // Cache each tile's offset within the track. Re-run on resize and on
  // tile-count changes so the rAF loop only ever reads cached numbers.
  useEffect(() => {
    const track = trackRef.current;
    if (!track || baseCount === 0) return;

    const refresh = () => {
      const tiles = Array.from(
        track.querySelectorAll<HTMLElement>("[data-marquee-tile]")
      );
      tileGeomRef.current = tiles.map((el) => ({
        el,
        centerInTrack: el.offsetLeft + el.offsetWidth / 2,
      }));
    };
    refresh();

    const observer = new ResizeObserver(refresh);
    observer.observe(track);
    return () => observer.disconnect();
  }, [baseCount, setWidth]);

  // Anchor the resting focal point at the viewport's horizontal center.
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const update = () => {
      const rect = el.getBoundingClientRect();
      const cx = rect.width / 2;
      if (focalRef.current < 0) focalRef.current = cx;
      if (!hoveringRef.current) focalTargetRef.current = cx;
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useAnimationFrame((_, delta) => {
    const width = setWidthRef.current;
    if (shouldReduceMotion || width <= 0) return;

    const dt = Math.min(delta / 1000, 0.05);

    // Frame-rate-independent glide: time-constant exponential smoothing.
    if (focalTargetRef.current >= 0) {
      const fT = 1 - Math.exp(-FOCAL_LERP_PER_SEC * dt);
      focalRef.current += (focalTargetRef.current - focalRef.current) * fT;
    }
    const sT = 1 - Math.exp(-SPEED_LERP_PER_SEC * dt);
    speedRef.current += (speedTargetRef.current - speedRef.current) * sT;
    intensityRef.current +=
      (intensityTargetRef.current - intensityRef.current) * sT;

    if (!pausedRef.current) {
      x.set(wrapX(x.get() - SPEED_PX_PER_SEC * dt * speedRef.current, width));
    }

    const trackX = x.get();
    const focalX = focalRef.current;
    const intensity = intensityRef.current;
    const tiles = tileGeomRef.current;
    for (let i = 0; i < tiles.length; i++) {
      const { el, centerInTrack } = tiles[i];
      const tileCenter = centerInTrack + trackX;
      const dist = Math.abs(tileCenter - focalX);
      const linear = Math.max(0, 1 - dist / FOCAL_RADIUS_PX);
      const eased = linear * linear * (3 - 2 * linear) * intensity;
      el.style.setProperty("--focal", eased.toFixed(3));
      el.style.zIndex = eased > 0.05 ? "2" : "1";
    }
  });

  if (baseCount === 0) return null;

  const updatePaused = () => {
    pausedRef.current =
      focusPausedRef.current ||
      dragPausedRef.current ||
      wheelPausedRef.current;
  };

  const recomputeSpeedTarget = () => {
    speedTargetRef.current = pausedRef.current
      ? 0
      : hoveringRef.current
        ? HOVER_SPEED_FACTOR
        : 1;
  };

  const setFocusPaused = (paused: boolean) => {
    focusPausedRef.current = paused;
    updatePaused();
    recomputeSpeedTarget();
  };
  const setDragPaused = (paused: boolean) => {
    dragPausedRef.current = paused;
    updatePaused();
    recomputeSpeedTarget();
  };
  const setWheelPaused = (paused: boolean) => {
    wheelPausedRef.current = paused;
    updatePaused();
    recomputeSpeedTarget();
  };

  const focalFromClientX = (clientX: number) => {
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return null;
    return Math.min(rect.width, Math.max(0, clientX - rect.left));
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
  // The horizontal mask fades tiles at the edges; the spotlight (driven by
  // per-tile --focal in CSS) lifts whichever tile sits closest to the focal
  // point. Vertical overflow stays visible so the lift + shadow aren't
  // clipped by the viewport box.
  return (
    <div
      ref={viewportRef}
      onPointerEnter={(event) => {
        hoveringRef.current = true;
        const fx = focalFromClientX(event.clientX);
        if (fx !== null) {
          focalTargetRef.current = fx;
          // Snap focal to pointer on enter so the lift originates under
          // the cursor instead of sweeping in from the previous position.
          focalRef.current = fx;
        }
        intensityTargetRef.current = 1;
        recomputeSpeedTarget();
      }}
      onPointerMove={(event) => {
        if (!hoveringRef.current) return;
        const fx = focalFromClientX(event.clientX);
        if (fx !== null) focalTargetRef.current = fx;
      }}
      onPointerLeave={() => {
        hoveringRef.current = false;
        intensityTargetRef.current = 0;
        recomputeSpeedTarget();
      }}
      onFocusCapture={(event) => {
        setFocusPaused(true);
        focusTile(event.target);
      }}
      onBlurCapture={() => setFocusPaused(false)}
      onWheel={handleWheel}
      className="py-6 [overflow-x:clip] [overflow-y:visible]"
      style={{
        WebkitMaskImage:
          "linear-gradient(to right, transparent 0%, black 12%, black 88%, transparent 100%)",
        maskImage:
          "linear-gradient(to right, transparent 0%, black 12%, black 88%, transparent 100%)",
      }}
    >
      <motion.div
        ref={trackRef}
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
        className="relative flex w-max cursor-grab active:cursor-grabbing [@media(hover:hover)]:[&:has(a:hover)_a:not(:hover)]:grayscale-[.5] [@media(hover:hover)]:[&:has(a:hover)_a:not(:hover)]:opacity-80 [&:has(a:focus-visible)_a:not(:focus-visible)]:grayscale-[.5] [&:has(a:focus-visible)_a:not(:focus-visible)]:opacity-80"
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
            progressiveBlur
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
