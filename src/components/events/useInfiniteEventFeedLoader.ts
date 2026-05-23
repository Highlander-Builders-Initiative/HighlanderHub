"use client";

import { useEffect, type RefObject } from "react";

type UseInfiniteEventFeedLoaderArgs = {
  loadMoreRef: RefObject<HTMLDivElement>;
  hasMore: boolean;
  loadError: string;
  isLoadingMore: boolean;
  isRestoring: boolean;
  onLoadMore: () => void;
};

export function useInfiniteEventFeedLoader({
  loadMoreRef,
  hasMore,
  loadError,
  isLoadingMore,
  isRestoring,
  onLoadMore,
}: UseInfiniteEventFeedLoaderArgs) {
  useEffect(() => {
    if (!hasMore || loadError || isLoadingMore || isRestoring) return;

    const target = loadMoreRef.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          void onLoadMore();
        }
      },
      { rootMargin: "640px 0px" }
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMore, loadError, isLoadingMore, isRestoring, loadMoreRef, onLoadMore]);
}
