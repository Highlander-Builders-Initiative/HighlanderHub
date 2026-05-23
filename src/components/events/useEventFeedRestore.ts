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
  const restoreState = useRef({
    snapshot: getSavedEventFeedSnapshotForRestore(),
    returnScroll: getSavedScrollPosition(),
    currentEvents: events,
    currentHasMore: initialHasMore,
    currentNextOffset: initialNextOffset,
  }).current;

  useLayoutEffect(() => {
    const {
      snapshot,
      returnScroll,
      currentEvents,
      currentHasMore,
      currentNextOffset,
    } = restoreState;
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
