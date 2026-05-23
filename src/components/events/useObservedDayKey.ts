"use client";

import { useEffect, useState, type MutableRefObject } from "react";

type UseObservedDayKeyArgs = {
  dayHeaderRefs: MutableRefObject<Map<string, HTMLElement>>;
  dayKeys: string[];
  userInitiatedScrollRef: MutableRefObject<number>;
  initialDayKey: string;
};

export function useObservedDayKey({
  dayHeaderRefs,
  dayKeys,
  userInitiatedScrollRef,
  initialDayKey,
}: UseObservedDayKeyArgs) {
  const [observedDayKey, setObservedDayKey] = useState(initialDayKey);

  useEffect(() => {
    if (dayKeys.length === 0) return;
    if (typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (Date.now() - userInitiatedScrollRef.current < 600) return;

        const candidates = entries
          .filter((entry) => entry.isIntersecting)
          .map((entry) => ({
            key: (entry.target as HTMLElement).dataset.dayKey ?? "",
            top: entry.boundingClientRect.top,
          }))
          .filter((candidate) => candidate.key)
          .sort((a, b) => a.top - b.top);

        if (candidates.length === 0) return;
        const next = candidates[0].key;
        setObservedDayKey((prev) => (prev === next ? prev : next));
      },
      { rootMargin: "0px 0px -80% 0px", threshold: 0 }
    );

    for (const el of dayHeaderRefs.current.values()) {
      observer.observe(el);
    }

    return () => observer.disconnect();
  }, [dayKeys, dayHeaderRefs, userInitiatedScrollRef]);

  return { observedDayKey, setObservedDayKey };
}
