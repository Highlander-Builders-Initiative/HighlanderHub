"use client";

import { useLayoutEffect, useState } from "react";
import type { CampusEvent } from "@/types/event";
import {
  readEventFeedRestoreState,
  type EventFeedRestoreState,
} from "@/lib/event-feed-session";
import {
  restoreSavedEventFeedSpot,
  type EventFeedRestorePatch,
} from "@/lib/event-feed-restore";

type RestoreBootstrap = EventFeedRestoreState & {
  currentEvents: CampusEvent[];
  currentHasMore: boolean;
  currentNextOffset: number;
};

type UseEventFeedRestoreArgs = {
  events: CampusEvent[];
  initialHasMore: boolean;
  initialNextOffset: number;
  applyRestore: (patch: EventFeedRestorePatch) => void;
};

export function useEventFeedRestore({
  events,
  initialHasMore,
  initialNextOffset,
  applyRestore,
}: UseEventFeedRestoreArgs) {
  const [isRestoring, setIsRestoring] = useState(false);
  const [bootstrap] = useState<RestoreBootstrap>(() => ({
    ...readEventFeedRestoreState(),
    currentEvents: events,
    currentHasMore: initialHasMore,
    currentNextOffset: initialNextOffset,
  }));

  useLayoutEffect(() => {
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
          applyRestore,
        });
      } finally {
        if (!cancelled) setIsRestoring(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    applyRestore,
  ]);

  return isRestoring;
}
