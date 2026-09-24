"use client";

import { useEffect, type RefObject } from "react";

// Overlays are bottom sheets below md; above it they are centered dialogs,
// which stay put.
const SHEET_MEDIA = "(max-width: 767px)";
// A slow release closes the sheet once it is pulled this far: a quarter of its
// height, capped so a tall sheet does not need a long pull.
const DISMISS_SHARE = 0.25;
const DISMISS_MAX_PX = 160;
// Release speeds in px/ms. A downward flick closes from any distance; an
// upward one keeps the sheet open even past the distance.
const FLICK_SPEED = 0.5;
const KEEP_SPEED = 0.3;
// The release speed is read over the drag's last stretch, so a finger that
// stops before lifting lets go at rest.
const VELOCITY_WINDOW_MS = 100;
// A release with a full sheet left to travel and no flick behind it. Reel
// paging settles in about this long; a flick shortens it, down to the floor,
// and a shorter leftover scales down so the sheet leaves at the same pace.
const SETTLE_SLOW_MS = 220;
const SETTLE_MIN_MS = 140;
const SETTLE_FULL_PX = 720;
// Per px/ms of release speed. A brisk flick (2 px/ms, 2000 px/s) divides the
// slow snap by about 1.4; a harder one hits the floor.
const SETTLE_FLICK_GAIN = 0.22;

type Sample = { y: number; t: number };

const clamp = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max);

/**
 * Timing for the sheet to travel `distance` px when released at `speed` (px/ms
 * toward the target). A full-height release with no speed takes about
 * SETTLE_SLOW_MS, and a faster flick finishes sooner. The ease-out is the iOS
 * one: steep at the start, so a finger that stopped still leaves immediately
 * instead of crawling off.
 */
function settleTiming(distance: number, speed: number) {
  const travel = Math.max(distance, 1);
  const pace = Math.max(speed, 0);
  const span = SETTLE_SLOW_MS * clamp(travel / SETTLE_FULL_PX, 0, 1);
  const duration = clamp(
    span / (1 + pace * SETTLE_FLICK_GAIN),
    SETTLE_MIN_MS,
    SETTLE_SLOW_MS
  );
  return {
    duration,
    easing: "cubic-bezier(0.32, 0.72, 0, 1)",
  };
}

/**
 * Pull-to-close for a bottom sheet, as on TikTok's and Instagram's sheets: with
 * its body scrolled to the top, pulling down drags the whole sheet with the
 * finger. Let go past a threshold, or flick, and it snaps off. A harder flick
 * finishes sooner; otherwise it settles back.
 *
 * The panel moves by `translate`, not `transform`, so the drag composes with
 * an open animation that holds the panel's transform (fill: both).
 */
export function useSheetSwipeDismiss({
  panelRef,
  scrollerRef,
  backdropRef,
  onDismiss,
}: {
  panelRef: RefObject<HTMLElement | null>;
  /** The sheet's scrolling body: a pull starts only at its top. */
  scrollerRef: RefObject<HTMLElement | null>;
  /** Fades with the pull. */
  backdropRef: RefObject<HTMLElement | null>;
  /** Runs once the sheet is off-screen. */
  onDismiss: () => void;
}) {
  useEffect(() => {
    const panel = panelRef.current;
    const scroller = scrollerRef.current;
    if (!panel || !scroller) return;
    const backdrop = backdropRef.current;
    const sheetMedia = window.matchMedia(SHEET_MEDIA);
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    let tracking = false;
    let dragging = false;
    let dismissing = false;
    let lastY = 0;
    // The finger's y when the sheet would sit at rest.
    let originY = 0;
    let offset = 0;
    let samples: Sample[] = [];
    let settling: Animation[] = [];

    const fadeFor = (y: number) => Math.max(0, 1 - y / panel.offsetHeight);

    const place = (y: number) => {
      offset = y;
      panel.style.translate = y > 0 ? `0 ${y}px` : "";
      if (backdrop) backdrop.style.opacity = y > 0 ? String(fadeFor(y)) : "";
    };

    const stopSettling = () => {
      settling.forEach((animation) => animation.cancel());
      settling = [];
    };

    const settle = (target: number, speed: number, onFinish: () => void) => {
      const { duration, easing } = settleTiming(Math.abs(target - offset), speed);
      const timing: KeyframeAnimationOptions = {
        duration: reducedMotion.matches ? 0 : duration,
        easing,
        fill: "forwards",
      };
      const sheet = panel.animate(
        [{ translate: `0 ${offset}px` }, { translate: `0 ${target}px` }],
        timing
      );
      settling = [sheet];
      if (backdrop) {
        settling.push(
          backdrop.animate(
            [{ opacity: fadeFor(offset) }, { opacity: fadeFor(target) }],
            timing
          )
        );
      }
      sheet.onfinish = onFinish;
    };

    const settleBack = (speed: number) => {
      if (offset <= 0) return;
      settle(0, speed, () => {
        place(0);
        stopSettling();
      });
    };

    const onTouchStart = (e: TouchEvent) => {
      if (dragging) {
        // A second finger: put the sheet back rather than guess.
        dragging = false;
        tracking = false;
        settleBack(0);
        return;
      }
      tracking = !dismissing && e.touches.length === 1 && sheetMedia.matches;
      if (!tracking) return;
      lastY = e.touches[0].clientY;
      samples = [{ y: lastY, t: e.timeStamp }];
      if (settling.length > 0) {
        // Caught on its way back: the finger holds it where it is.
        const [, y = "0"] = getComputedStyle(panel).translate.split(" ");
        stopSettling();
        place(parseFloat(y) || 0);
        dragging = offset > 0;
        originY = lastY - offset;
      }
    };

    const onTouchMove = (e: TouchEvent) => {
      if (!tracking) return;
      const y = e.touches[0].clientY;
      if (!dragging) {
        const dy = y - lastY;
        lastY = y;
        // The pull claims a touch heading down with the body at its top. A
        // touch already scrolling the body hands over there when the browser
        // still lets it be cancelled (iOS); Chrome commits a touch to its
        // scroll, so there the pull waits for the next touch.
        if (dy <= 0 || scroller.scrollTop > 0 || !e.cancelable) return;
        dragging = true;
        originY = y - dy;
        samples = [];
      }
      e.preventDefault();
      place(Math.max(0, y - originY));
      samples.push({ y, t: e.timeStamp });
      if (samples.length > 16) samples.shift();
    };

    const onTouchEnd = (e: TouchEvent) => {
      if (!tracking) return;
      tracking = false;
      if (!dragging) return;
      dragging = false;

      const end = { y: e.changedTouches[0].clientY, t: e.timeStamp };
      const first = [...samples, end].find(
        (sample) => end.t - sample.t <= VELOCITY_WINDOW_MS
      );
      const velocity =
        first && first !== end ? (end.y - first.y) / Math.max(end.t - first.t, 1) : 0;

      const height = panel.offsetHeight;
      const threshold = Math.min(height * DISMISS_SHARE, DISMISS_MAX_PX);
      if (velocity > FLICK_SPEED || (velocity > -KEEP_SPEED && offset > threshold)) {
        dismissing = true;
        settle(height, velocity, () => onDismiss());
      } else {
        settleBack(-velocity);
      }
    };

    const onTouchCancel = () => {
      tracking = false;
      if (!dragging) return;
      dragging = false;
      settleBack(0);
    };

    panel.addEventListener("touchstart", onTouchStart, { passive: true });
    panel.addEventListener("touchmove", onTouchMove, { passive: false });
    panel.addEventListener("touchend", onTouchEnd, { passive: true });
    panel.addEventListener("touchcancel", onTouchCancel, { passive: true });
    return () => {
      panel.removeEventListener("touchstart", onTouchStart);
      panel.removeEventListener("touchmove", onTouchMove);
      panel.removeEventListener("touchend", onTouchEnd);
      panel.removeEventListener("touchcancel", onTouchCancel);
    };
  }, [panelRef, scrollerRef, backdropRef, onDismiss]);
}
