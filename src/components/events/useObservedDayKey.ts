"use client";

import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";
import { SCROLL_SPY_OFFSET_PX, resolveObservedDayKey } from "@/lib/events/observed-day-key";

type UseObservedDayKeyArgs = {
  dayHeaderRefs: MutableRefObject<Map<string, HTMLElement>>;
  daySectionRefs?: MutableRefObject<Map<string, HTMLElement>>;
  dayKeys: string[];
  userInitiatedScrollRef: MutableRefObject<number>;
  initialDayKey: string;
};

export function useObservedDayKey({
  dayHeaderRefs,
  daySectionRefs,
  dayKeys,
  userInitiatedScrollRef,
  initialDayKey,
}: UseObservedDayKeyArgs) {
  const [observedDayKey, setObservedDayKeyState] = useState(
    () => dayKeys[0] ?? initialDayKey
  );
  // Scroll can resolve the same day every frame; skip setState so this
  // owner does not re-render (React still renders once even on a bailout).
  const observedDayKeyRef = useRef(observedDayKey);
  const setObservedDayKey = useCallback((next: string) => {
    if (observedDayKeyRef.current === next) return;
    observedDayKeyRef.current = next;
    setObservedDayKeyState(next);
  }, []);

  // Whether the feed has scrolled past its first day heading (up to the spy
  // line, just under the search bar). The desktop bar names the observed day
  // from then on; above it, the first heading is in plain view. Keyed to the
  // first heading rather than the observed day's own, which can still be down
  // the page once the previous day has scrolled away.
  const [pastFirstDayHeading, setPastFirstDayHeadingState] = useState(false);
  const pastFirstDayHeadingRef = useRef(false);
  const setPastFirstDayHeading = useCallback((next: boolean) => {
    if (pastFirstDayHeadingRef.current === next) return;
    pastFirstDayHeadingRef.current = next;
    setPastFirstDayHeadingState(next);
  }, []);

  useEffect(() => {
    if (dayKeys.length === 0) return;

    let rafId = 0;

    const update = () => {
      const firstHeader = dayHeaderRefs.current.get(dayKeys[0]);
      setPastFirstDayHeading(
        !!firstHeader && firstHeader.getBoundingClientRect().top <= SCROLL_SPY_OFFSET_PX
      );

      if (Date.now() - userInitiatedScrollRef.current < 600) return;

      const headerTopByKey = new Map<string, number>();
      const sectionBottomByKey = new Map<string, number>();

      for (const key of dayKeys) {
        const header = dayHeaderRefs.current.get(key);
        if (header) {
          headerTopByKey.set(key, header.getBoundingClientRect().top);
        }
        const section = daySectionRefs?.current.get(key);
        if (section) {
          sectionBottomByKey.set(key, section.getBoundingClientRect().bottom);
        }
      }

      const next = resolveObservedDayKey({
        dayKeys,
        headerTopByKey,
        sectionBottomByKey,
        viewportHeight: window.innerHeight,
      });

      if (next) setObservedDayKey(next);
    };

    const onScroll = () => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(update);
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    update();

    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      cancelAnimationFrame(rafId);
    };
  }, [
    dayKeys,
    dayHeaderRefs,
    daySectionRefs,
    userInitiatedScrollRef,
    setObservedDayKey,
    setPastFirstDayHeading,
  ]);

  return { observedDayKey, setObservedDayKey, pastFirstDayHeading };
}
