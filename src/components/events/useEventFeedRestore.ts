"use client";

import {
  useLayoutEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import type { CampusEvent, EventCategory } from "@/types/event";
import type { DayWindow } from "./events-filters";
import {
  getSavedEventFeedSnapshotForRestore,
  getSavedScrollPosition,
} from "@/lib/event-feed-session";
import { restoreSavedEventFeedSpot } from "@/lib/event-feed-restore";

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
  const restoreState = useRef<{
    snapshot: ReturnType<typeof getSavedEventFeedSnapshotForRestore>;
    returnScroll: ReturnType<typeof getSavedScrollPosition>;
    currentEvents: CampusEvent[];
    currentHasMore: boolean;
    currentNextOffset: number;
    setCategory: Dispatch<SetStateAction<EventCategory | "all">>;
    setQuery: Dispatch<SetStateAction<string>>;
    setDayWindow: Dispatch<SetStateAction<DayWindow>>;
    setLoadedEvents: Dispatch<SetStateAction<CampusEvent[]>>;
    setHasMore: Dispatch<SetStateAction<boolean>>;
    setNextOffset: Dispatch<SetStateAction<number>>;
  } | null>(null);

  if (restoreState.current === null) {
    restoreState.current = {
      snapshot: getSavedEventFeedSnapshotForRestore(),
      returnScroll: getSavedScrollPosition(),
      currentEvents: events,
      currentHasMore: initialHasMore,
      currentNextOffset: initialNextOffset,
      setCategory,
      setQuery,
      setDayWindow,
      setLoadedEvents,
      setHasMore,
      setNextOffset,
    };
  }

  useLayoutEffect(() => {
    const restore = restoreState.current;
    if (!restore) return;

    const {
      snapshot,
      returnScroll,
      currentEvents,
      currentHasMore,
      currentNextOffset,
      setCategory,
      setQuery,
      setDayWindow,
      setLoadedEvents,
      setHasMore,
      setNextOffset,
    } = restore;
    if (!snapshot && !returnScroll) return;

    const path = `${window.location.pathname}${window.location.search}`;
    if (snapshot && snapshot.path !== path) return;
    if (!snapshot && returnScroll?.path !== path) return;

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
  }, []);

  return isRestoring;
}
