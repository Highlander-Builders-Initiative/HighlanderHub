"use client";

import { useEffect, type MutableRefObject, type RefObject } from "react";
import { FEED_LOOKAHEAD_VIEWPORTS } from "./useNearViewport";

type UseInfiniteEventFeedLoaderArgs = {
  loadMoreRef: RefObject<HTMLDivElement | null>;
  hasMore: boolean;
  loadError: string;
  isLoadingMore: boolean;
  isRestoring: boolean;
  onLoadMore: () => void;
  suppressAutoLoadUntilRef?: MutableRefObject<number>;
  pendingCalendarScrollRef?: MutableRefObject<string | null>;
};

export function useInfiniteEventFeedLoader({
  loadMoreRef,
  hasMore,
  loadError,
  isLoadingMore,
  isRestoring,
  onLoadMore,
  suppressAutoLoadUntilRef,
  pendingCalendarScrollRef,
}: UseInfiniteEventFeedLoaderArgs) {
  useEffect(() => {
    if (!hasMore || loadError || isLoadingMore || isRestoring) return;

    const target = loadMoreRef.current;
    if (!target) return;
    const observedTarget: HTMLDivElement = target;
    let retryTimeoutId: number | null = null;

    // The next page lands while the feed's end is still screens away, so its
    // cards, and their flyers, are ready before the reader reaches them.
    function isWithinLoadMargin() {
      const margin = window.innerHeight * FEED_LOOKAHEAD_VIEWPORTS;
      const rect = observedTarget.getBoundingClientRect();
      return rect.top <= window.innerHeight + margin && rect.bottom >= -margin;
    }

    function clearRetry() {
      if (retryTimeoutId === null) return;
      window.clearTimeout(retryTimeoutId);
      retryTimeoutId = null;
    }

    function scheduleRetry() {
      if (retryTimeoutId !== null) return;
      const suppressUntil = suppressAutoLoadUntilRef?.current ?? 0;
      const delay = Math.max(50, suppressUntil - Date.now() + 50);
      retryTimeoutId = window.setTimeout(() => {
        retryTimeoutId = null;
        if (isWithinLoadMargin()) tryLoadOrDefer();
      }, delay);
    }

    function tryLoadOrDefer() {
      if (pendingCalendarScrollRef?.current) {
        scheduleRetry();
        return;
      }
      if (
        suppressAutoLoadUntilRef &&
        Date.now() < suppressAutoLoadUntilRef.current
      ) {
        scheduleRetry();
        return;
      }

      clearRetry();
      void onLoadMore();
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          tryLoadOrDefer();
        }
      },
      { rootMargin: `${FEED_LOOKAHEAD_VIEWPORTS * 100}% 0px` }
    );

    observer.observe(observedTarget);
    return () => {
      clearRetry();
      observer.disconnect();
    };
  }, [
    hasMore,
    loadError,
    isLoadingMore,
    isRestoring,
    loadMoreRef,
    onLoadMore,
    suppressAutoLoadUntilRef,
    pendingCalendarScrollRef,
  ]);
}
