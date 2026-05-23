"use client";

import {
  useLayoutEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import type { CampusEvent, EventCategory } from "@/types/event";
import type { DayWindow } from "@/types/events-feed";
import {
  getSavedEventFeedSnapshotForRestore,
  getSavedScrollPosition,
} from "@/lib/event-feed-session";
import { restoreSavedEventFeedSpot } from "@/lib/event-feed-restore";

type RestoreBootstrap = {
  snapshot: ReturnType<typeof getSavedEventFeedSnapshotForRestore>;
  returnScroll: ReturnType<typeof getSavedScrollPosition>;
  currentEvents: CampusEvent[];
  currentHasMore: boolean;
  currentNextOffset: number;
};

type UseEventFeedRestoreArgs = {
  events: CampusEvent[];
  initialHasMore: boolean;
  initialNextOffset: number;
  setCategory: Dispatch<SetStateAction<EventCategory | "all">>;
  setQuery: Dispatch<SetStateAction<string>>;
  setDayWindow: Dispatch<SetStateAction<DayWindow>>;
  setLoadedEvents: Dispatch<SetStateAction<CampusEvent[]>>;
  setHasMore: Dispatch<SetStateAction<boolean>>;
  setNextOffset: Dispatch<SetStateAction<number>>;
};

export function useEventFeedRestore({
  events,
  initialHasMore,
  initialNextOffset,
  setCategory,
  setQuery,
  setDayWindow,
  setLoadedEvents,
  setHasMore,
  setNextOffset,
}: UseEventFeedRestoreArgs) {
  const [isRestoring, setIsRestoring] = useState(false);
  const bootstrapRef = useRef<RestoreBootstrap | null>(null);

  if (bootstrapRef.current === null) {
    bootstrapRef.current = {
      snapshot: getSavedEventFeedSnapshotForRestore(),
      returnScroll: getSavedScrollPosition(),
      currentEvents: events,
      currentHasMore: initialHasMore,
      currentNextOffset: initialNextOffset,
    };
  }

  useLayoutEffect(() => {
    const bootstrap = bootstrapRef.current;
    if (!bootstrap) return;

    const {
      snapshot,
      returnScroll,
      currentEvents,
      currentHasMore,
      currentNextOffset,
    } = bootstrap;
    if (!snapshot && !returnScroll) return;

    const path = `${window.location.pathname}${window.location.search}`;
    let cancelled = false;
    setIsRestoring(true);

    void (async () => {
      try {
        await restoreSavedEventFeedSpot({
          snapshot,
          returnScroll,
          path,
          currentEvents,
          currentHasMore,
          currentNextOffset,
          setCategory,
          setQuery,
          setDayWindow,
          setLoadedEvents,
          setHasMore,
          setNextOffset,
        });
      } finally {
        if (!cancelled) setIsRestoring(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    setCategory,
    setQuery,
    setDayWindow,
    setLoadedEvents,
    setHasMore,
    setNextOffset,
  ]);

  return isRestoring;
}
