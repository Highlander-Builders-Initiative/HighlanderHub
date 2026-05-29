"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { CampusEvent } from "@/types/event";
import type { EventFilterCountSource } from "@/types/events-feed";
import { fetchEventsByIds } from "@/lib/events/api";
import { computeMissingSearchIds } from "./events-filters";

// Matches deeper in the feed than this are not backfilled; the earliest ones
// (the corpus is chronological) are shown alongside whatever's already loaded.
// Mirrors EVENTS_BY_IDS_LIMIT on the server.
const MAX_BACKFILL = 200;
const EMPTY: CampusEvent[] = [];

type Args = {
  query: string;
  filterCountSource: EventFilterCountSource[];
  loadedEvents: CampusEvent[];
};

/**
 * Search runs client-side over `loadedEvents`, but the feed paginates — a match
 * the student hasn't scrolled to yet would never surface. The full count source
 * already lists every upcoming event, so when a query is active we resolve the
 * full records for matching ids that aren't loaded and hand them back to be
 * merged into the rendered feed. Fetched records are cached for the session, so
 * re-searching a term never re-hits the network.
 */
export function useEventSearchBackfill({
  query,
  filterCountSource,
  loadedEvents,
}: Args): CampusEvent[] {
  const normalizedQuery = query.trim().toLowerCase();
  const [fetched, setFetched] = useState<Map<string, CampusEvent>>(
    () => new Map()
  );
  const inFlightRef = useRef<Set<string>>(new Set());

  const loadedIds = useMemo(
    () => new Set(loadedEvents.map((event) => event.id)),
    [loadedEvents]
  );

  const missingIds = useMemo(
    () =>
      computeMissingSearchIds(
        filterCountSource,
        normalizedQuery,
        loadedIds,
        MAX_BACKFILL
      ),
    [filterCountSource, normalizedQuery, loadedIds]
  );

  useEffect(() => {
    const toFetch = missingIds.filter(
      (id) => !fetched.has(id) && !inFlightRef.current.has(id)
    );
    if (toFetch.length === 0) return;

    let cancelled = false;
    toFetch.forEach((id) => inFlightRef.current.add(id));
    fetchEventsByIds(toFetch)
      .then((events) => {
        if (cancelled || events.length === 0) return;
        setFetched((prev) => {
          const next = new Map(prev);
          for (const event of events) next.set(event.id, event);
          return next;
        });
      })
      // Swallow: on failure search still shows the matches already loaded.
      .catch(() => {})
      .finally(() => {
        toFetch.forEach((id) => inFlightRef.current.delete(id));
      });

    return () => {
      cancelled = true;
    };
  }, [missingIds, fetched]);

  return useMemo(() => {
    if (missingIds.length === 0) return EMPTY;
    const events: CampusEvent[] = [];
    for (const id of missingIds) {
      const event = fetched.get(id);
      if (event) events.push(event);
    }
    return events.length === 0 ? EMPTY : events;
  }, [missingIds, fetched]);
}
