"use client";

import { useEffect, type MutableRefObject, type RefObject } from "react";

const LOAD_ROOT_MARGIN_PX = 640;

type UseInfiniteEventFeedLoaderArgs = {
  loadMoreRef: RefObject<HTMLDivElement>;
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

    function isWithinLoadMargin() {
      const rect = observedTarget.getBoundingClientRect();
      return (
        rect.top <= window.innerHeight + LOAD_ROOT_MARGIN_PX &&
        rect.bottom >= -LOAD_ROOT_MARGIN_PX
      );
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
      { rootMargin: `${LOAD_ROOT_MARGIN_PX}px 0px` }
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
