"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { CampusEvent } from "@/types/event";
import { groupByDay } from "@/lib/events/grouping";
import { formatPacificDayKey, pacificTodayKey } from "@/lib/dates";
import { EventCard } from "./EventCard";
import { useSavedEvents } from "./useSavedEvents";

type Status = "loading" | "ready" | "error";

export function SavedEventsClient() {
  const { savedIds } = useSavedEvents();
  const [events, setEvents] = useState<CampusEvent[]>([]);
  const [status, setStatus] = useState<Status>("loading");

  // Re-resolve whenever the saved set changes (keyed by the joined ids). The
  // batch endpoint reuses the per-id Data Cache, so repeat loads are cheap.
  const key = savedIds.join(",");
  useEffect(() => {
    let ignore = false;
    if (savedIds.length === 0) {
      setEvents([]);
      setStatus("ready");
      return;
    }
    setStatus("loading");
    fetch(`/api/events/by-ids?ids=${encodeURIComponent(key)}`)
      .then((res) => {
        if (!res.ok) throw new Error("by-ids failed");
        return res.json();
      })
      .then((data: { events?: CampusEvent[] }) => {
        if (!ignore) {
          setEvents(data.events ?? []);
          setStatus("ready");
        }
      })
      .catch(() => {
        if (!ignore) setStatus("error");
      });
    return () => {
      ignore = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // Filter by the live saved set so an un-save removes the row immediately,
  // without waiting for the refetch to land.
  const visible = useMemo(
    () => events.filter((event) => savedIds.includes(event.id)),
    [events, savedIds]
  );
  const todayKey = useMemo(() => pacificTodayKey(), []);
  const dayGroups = useMemo(() => {
    const grouped = groupByDay(visible);
    return [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [visible]);

  if (status === "error") {
    return (
      <p className="text-sm text-coral" role="status">
        Couldn&rsquo;t load your saved events. Refresh to try again.
      </p>
    );
  }

  if (status === "loading" && visible.length === 0) {
    return (
      <p className="text-sm text-muted" role="status">
        Loading your saved events…
      </p>
    );
  }

  if (savedIds.length === 0) {
    return (
      <div className="py-10">
        <p className="max-w-[42ch] font-display text-2xl font-semibold leading-[1.2] tracking-[-0.02em] text-ink">
          Nothing saved yet.
        </p>
        <p className="mt-3 max-w-[52ch] text-[15px] leading-[1.55] text-ink/70">
          Tap the heart on any event to keep it here for later.
        </p>
        <Link
          href="/events"
          className="interactive-focus mt-7 inline-flex min-h-11 items-center rounded-lg bg-ink px-5 py-2 text-sm font-medium text-canvas transition-opacity hover:opacity-85"
        >
          Browse events
        </Link>
      </div>
    );
  }

  return (
    <div>
      {dayGroups.map(([day, dayEvents]) => (
        <div
          key={day}
          className="mb-10 border-t border-ink/15 pt-7 first:border-t-0 first:pt-0"
        >
          <h2 className="mb-4 flex items-baseline gap-2.5 font-display text-lg font-semibold tracking-[-0.02em] text-ink">
            {formatPacificDayKey(day)}
            {day === todayKey && (
              <span className="font-body text-[12px] font-medium text-ink/55">
                Today
              </span>
            )}
          </h2>
          <div className="flex flex-col gap-2.5">
            {dayEvents.map((event) => (
              <EventCard key={event.id} event={event} saveSurface="saved_page" />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
