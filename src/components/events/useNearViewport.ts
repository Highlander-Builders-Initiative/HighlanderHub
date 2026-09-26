"use client";

import { useEffect, useState, type RefObject } from "react";

/**
 * How far ahead of the reader, in screens, the feed gets ready: it appends the
 * next page, and starts each card's flyer, once they are this close. A fast
 * phone scroll covers a few thousand px a second and an uncached flyer takes
 * up to a second, so the browser's own lazy distance (about 1250px in Chrome)
 * leaves slots shimmering as they arrive.
 */
export const FEED_LOOKAHEAD_VIEWPORTS = 3;

// One observer for every card. A card is watched until it first comes near.
let observer: IntersectionObserver | null = null;
const onNear = new Map<Element, () => void>();

function observeUntilNear(el: Element, callback: () => void) {
  observer ??= new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) onNear.get(entry.target)?.();
      }
    },
    { rootMargin: `${FEED_LOOKAHEAD_VIEWPORTS * 100}% 0px` }
  );
  onNear.set(el, callback);
  observer.observe(el);
  return () => {
    onNear.delete(el);
    observer?.unobserve(el);
  };
}

/**
 * True once the element comes within the feed's look-ahead of the viewport,
 * and from then on. Observe the card itself: it has layout even while
 * content-visibility skips its contents.
 */
export function useNearViewport(ref: RefObject<Element | null>) {
  const [near, setNear] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (near || !el) return;
    return observeUntilNear(el, () => setNear(true));
  }, [near, ref]);
  return near;
}
