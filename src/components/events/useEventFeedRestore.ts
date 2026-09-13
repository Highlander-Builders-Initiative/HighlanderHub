"use client";

import { useLayoutEffect, useState } from "react";
import type { CampusEvent } from "@/types/event";
import {
  readEventFeedRestoreState,
  type EventFeedRestoreState,
} from "@/lib/events/feed-session";
import {
  restoreSavedEventFeedSpot,
  type EventFeedRestorePatch,
} from "@/lib/events/feed-restore";
import type { EventFeedQuery } from "@/components/events/events-filters";

type RestoreBootstrap = EventFeedRestoreState & {
  currentEvents: CampusEvent[];
  currentHasMore: boolean;
  currentNextOffset: number;
  pageFilters: EventFeedQuery;
};

type UseEventFeedRestoreArgs = {
  events: CampusEvent[];
  initialHasMore: boolean;
  initialNextOffset: number;
  pageFilters: EventFeedQuery;
  applyRestore: (patch: EventFeedRestorePatch) => void;
};

export function useEventFeedRestore({
  events,
  initialHasMore,
  initialNextOffset,
  pageFilters,
  applyRestore,
}: UseEventFeedRestoreArgs) {
  const [isRestoring, setIsRestoring] = useState(false);
  const [bootstrap] = useState<RestoreBootstrap>(() => ({
    ...readEventFeedRestoreState(),
    currentEvents: events,
    currentHasMore: initialHasMore,
    currentNextOffset: initialNextOffset,
    pageFilters,
  }));

  useLayoutEffect(() => {
    const {
      snapshot,
      returnScroll,
      currentEvents,
      currentHasMore,
      currentNextOffset,
      pageFilters,
    } = bootstrap;
    if (!snapshot && !returnScroll) return;

    const path = `${window.location.pathname}${window.location.search}`;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- restore is an external session handshake
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
          pageFilters,
          applyRestore,
        });
      } finally {
        if (!cancelled) setIsRestoring(false);
      }
    })();

    return () => {
      cancelled = true;
    };
    // `bootstrap` is a one-time snapshot (useState initializer, no setter) so it
    // is referentially stable; listing it satisfies the linter without re-runs.
  }, [applyRestore, bootstrap]);

  return isRestoring;
}
