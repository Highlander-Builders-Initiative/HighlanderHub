"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  logoutAdmin,
  updateEvent,
  deleteEvent,
  mergeDuplicateEvents,
  markEventsDifferent,
} from "../actions";
import { useRouter } from "next/navigation";
import { IoLogOutOutline, IoOpenOutline, IoSearchOutline } from "react-icons/io5";
import clsx from "clsx";
import Link from "next/link";
import { isPublicContentKind } from "@/lib/events/content-kind";
import { AdminLiveEventRow } from "../AdminLiveEventRow";
import { AdminEventEditDrawer } from "../AdminEventEditDrawer";
import { AdminDuplicateReview } from "../AdminDuplicateReview";
import { useAdminActions } from "../useAdminActions";
import type { MergeFieldChoice } from "../duplicate-merge";
import {
  actionErrorFor,
  isEventActionPending,
  isEventUpdatePending,
} from "../pending-action";
import {
  type AdminEventFilterKey,
  type AdminEventRow,
  type AdminEventUpdatePayload,
  type DuplicateReviewPair,
  ADMIN_EVENT_FILTERS,
  duplicatePairKey,
  sortEventsByFeedOrder,
  matchesAdminQuery,
} from "../types";

interface AdminDashboardClientProps {
  initialEvents: AdminEventRow[];
  /** Set when the live-events read failed; initialEvents is then empty. */
  eventsError: string | null;
  duplicatePairs: DuplicateReviewPair[];
  duplicateQueueError: string | null;
}

export default function AdminDashboardClient({
  initialEvents,
  eventsError,
  duplicatePairs,
  duplicateQueueError,
}: AdminDashboardClientProps) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<AdminEventFilterKey[]>([]);
  const [editingEventId, setEditingEventId] = useState<string | null>(null);
  // Decided pairs and removed listings leave at once; the refresh that
  // follows confirms it. A failed decision brings its pair back.
  const [decidedPairs, setDecidedPairs] = useState<string[]>([]);
  const [removedEvents, setRemovedEvents] = useState<string[]>([]);
  const searchRef = useRef<HTMLInputElement>(null);
  const { pendingAction, actionError, setActionError, runAction } =
    useAdminActions();

  const liveEvents = useMemo(
    () => initialEvents.filter((event) => !removedEvents.includes(event.id)),
    [initialEvents, removedEvents]
  );
  const editingEvent = useMemo(
    () => liveEvents.find((e) => e.id === editingEventId) ?? null,
    [liveEvents, editingEventId]
  );
  const openPairs = useMemo(
    () =>
      duplicatePairs.filter(
        (pair) =>
          !decidedPairs.includes(duplicatePairKey(pair)) &&
          !removedEvents.includes(pair.first.id) &&
          !removedEvents.includes(pair.second.id)
      ),
    [duplicatePairs, decidedPairs, removedEvents]
  );

  // "/" jumps to search, as in most admin tools.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey || e.defaultPrevented) return;
      const target = e.target instanceof Element ? e.target : null;
      if (target?.closest("input, textarea, select, [contenteditable=\"true\"]")) return;
      if (document.querySelector("dialog[open]")) return;
      e.preventDefault();
      searchRef.current?.focus();
      searchRef.current?.select();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const handleLogout = () => {
    void runAction({ type: "logout" }, async () => {
      await logoutAdmin();
      router.push("/admin/login");
      router.refresh();
    });
  };

  const handleSave = (payload: AdminEventUpdatePayload) => {
    if (!editingEventId) return;
    const eventId = editingEventId;
    void runAction({ type: "update", id: eventId }, async () => {
      const res = await updateEvent(eventId, payload);
      if (res.success) {
        setEditingEventId(null);
        router.refresh();
      } else {
        setActionError({
          action: { type: "update", id: eventId },
          message: res.error || "Failed to update event.",
        });
      }
    });
  };

  const handleDelete = (event: AdminEventRow) => {
    if (
      !confirm(
        `Delete "${event.title}" from the public calendar? This cannot be undone.`
      )
    )
      return;
    const action = { type: "delete" as const, id: event.id };
    void runAction(action, async () => {
      const res = await deleteEvent(event.id);
      if (res.success) {
        setRemovedEvents((ids) => [...ids, event.id]);
        router.refresh();
      } else {
        setActionError({ action, message: res.error || "Failed to delete event." });
      }
    });
  };

  // Shared by merge and "different events": hide the pair now, and bring it
  // back with its error if the decision doesn't go through.
  const decide = async (
    action: { type: "merge" | "distinct"; id: string },
    fn: () => Promise<{ success: boolean; error?: string }>,
    fallback: string,
    onSuccess?: () => void
  ) => {
    const restore = () =>
      setDecidedPairs((keys) => keys.filter((key) => key !== action.id));
    setDecidedPairs((keys) => [...keys, action.id]);
    const completed = await runAction(action, async () => {
      const res = await fn();
      if (res.success) {
        onSuccess?.();
        router.refresh();
      } else {
        restore();
        setActionError({ action, message: res.error || fallback });
      }
    });
    if (!completed) restore();
  };

  const handleMerge = (
    pairKey: string,
    kept: AdminEventRow,
    removed: AdminEventRow,
    takes: MergeFieldChoice[]
  ) =>
    void decide(
      { type: "merge", id: pairKey },
      () =>
        mergeDuplicateEvents(
          kept.id,
          removed.id,
          { kept: kept.updated_at, removed: removed.updated_at },
          takes
        ),
      "Failed to merge events.",
      () => setRemovedEvents((ids) => [...ids, removed.id])
    );

  const handleDistinct = (pairKey: string, pair: DuplicateReviewPair) =>
    void decide(
      { type: "distinct", id: pairKey },
      () => markEventsDifferent(pair.first.id, pair.second.id),
      "Failed to save the decision."
    );

  const eventsInFeedOrder = useMemo(() => sortEventsByFeedOrder(liveEvents), [liveEvents]);
  // The # labels count only what the public feed shows.
  const feedPositionById = useMemo(
    () =>
      new Map(
        eventsInFeedOrder
          .filter((event) => isPublicContentKind(event.content_kind))
          .map((event, index) => [event.id, index])
      ),
    [eventsInFeedOrder]
  );
  const filterCounts = useMemo(
    () =>
      Object.fromEntries(
        ADMIN_EVENT_FILTERS.map((filter) => [
          filter.key,
          liveEvents.filter(filter.test).length,
        ])
      ) as Record<AdminEventFilterKey, number>,
    [liveEvents]
  );
  const filteredEvents = eventsInFeedOrder.filter(
    (event) =>
      matchesAdminQuery(search, event) &&
      ADMIN_EVENT_FILTERS.every(
        (filter) => !filters.includes(filter.key) || filter.test(event)
      )
  );
  const narrowed = search.trim() !== "" || filters.length > 0;
  const toggleFilter = (key: AdminEventFilterKey) =>
    setFilters((keys) =>
      keys.includes(key) ? keys.filter((k) => k !== key) : [...keys, key]
    );
  const globalError = actionErrorFor(actionError, ["logout"]);

  return (
    <div className="min-h-screen bg-surface flex flex-col font-sans text-ink">
      <header className="sticky top-0 bg-canvas border-b border-ink/10 z-40">
        <div className="h-14 px-4 sm:px-6 flex items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="font-display text-lg font-semibold tracking-tight text-ink">
                Admin
              </h1>
              <span className="text-muted text-sm font-sans hidden sm:inline">
                · Highlander Hub
              </span>
            </div>
            <p className="text-[0.6875rem] text-muted font-sans truncate sm:max-w-none">
              Manage live events
            </p>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <Link
              href="/events"
              target="_blank"
              className="flex items-center gap-1.5 text-xs text-muted hover:text-ink font-sans py-2 px-2.5 sm:px-3 hover:bg-surface border border-transparent hover:border-ink/5 rounded-md outline-none interactive-focus press"
            >
              <IoOpenOutline size={15} aria-hidden />
              <span className="hidden sm:inline">View site</span>
            </Link>
            <button
              onClick={handleLogout}
              disabled={pendingAction?.type === "logout"}
              className="flex items-center gap-1.5 text-xs text-muted hover:text-ink font-sans py-2 px-2.5 sm:px-3 hover:bg-surface border border-transparent hover:border-ink/5 rounded-md outline-none interactive-focus press disabled:opacity-50"
            >
              <IoLogOutOutline size={15} aria-hidden />
              <span>Sign out</span>
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 w-full max-w-6xl mx-auto p-4 sm:p-6 space-y-6">
        {globalError && (
          <div
            role="alert"
            className="p-4 bg-coral/10 border border-deep-coral/20 text-deep-coral rounded-md text-sm font-sans flex items-start gap-2 animate-field-reveal"
          >
            <p className="flex-1 font-sans">{globalError}</p>
            <button
              type="button"
              onClick={() => setActionError(null)}
              className="text-deep-coral hover:text-ink outline-none interactive-focus press font-bold"
              aria-label="Dismiss error"
            >
              ×
            </button>
          </div>
        )}

        <AdminDuplicateReview
          pairs={openPairs}
          queueError={duplicateQueueError}
          feedPositionById={feedPositionById}
          pendingAction={pendingAction}
          actionError={actionError}
          onMerge={handleMerge}
          onDistinct={handleDistinct}
          onEdit={(event) => setEditingEventId(event.id)}
        />

        <section aria-labelledby="live-events-heading" className="space-y-4">
          <div className="space-y-3 border-b border-ink/10 pb-3 pt-4">
            <div className="flex items-baseline justify-between gap-4">
              <h2
                id="live-events-heading"
                className="font-display text-base font-semibold text-ink"
              >
                Live events
              </h2>
              {!eventsError && (
                <p className="text-[0.6875rem] text-muted tabular-nums" aria-live="polite">
                  {narrowed
                    ? `Showing ${filteredEvents.length} of ${liveEvents.length}`
                    : `${liveEvents.length} upcoming`}
                </p>
              )}
            </div>

            <div className="relative max-w-md">
              <IoSearchOutline
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted/50 pointer-events-none"
                size={14}
                aria-hidden
              />
              <input
                ref={searchRef}
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Escape" && search) {
                    e.preventDefault();
                    setSearch("");
                  }
                }}
                aria-label="Search live events"
                aria-keyshortcuts="/"
                placeholder="Search, paste an Instagram link, or @handle"
                autoComplete="off"
                spellCheck={false}
                className="w-full bg-canvas border border-ink/15 rounded-md pl-9 pr-9 py-2 text-base placeholder:text-muted/50 transition-colors focus:border-ink outline-none interactive-focus"
              />
              {!search && (
                <kbd
                  aria-hidden
                  className="absolute right-3 top-1/2 -translate-y-1/2 hidden sm:block rounded border border-ink/15 px-1 font-sans text-[0.6875rem] text-muted pointer-events-none"
                >
                  /
                </kbd>
              )}
            </div>

            <div role="group" aria-label="Filters" className="flex flex-wrap gap-2">
              {ADMIN_EVENT_FILTERS.map((filter) => {
                const on = filters.includes(filter.key);
                return (
                  <button
                    key={filter.key}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggleFilter(filter.key)}
                    className={clsx(
                      "min-h-8 px-2.5 rounded-full border text-xs font-sans inline-flex items-center gap-1.5 outline-none interactive-focus press transition-colors",
                      on
                        ? "bg-ink text-canvas border-ink"
                        : "bg-canvas text-muted border-ink/15 hover:text-ink hover:border-ink/30"
                    )}
                  >
                    {filter.label}
                    <span className={clsx("tabular-nums", on ? "text-canvas/70" : "text-faint")}>
                      {filterCounts[filter.key]}
                    </span>
                  </button>
                );
              })}
              {narrowed && (
                <button
                  type="button"
                  onClick={() => {
                    setSearch("");
                    setFilters([]);
                  }}
                  className="min-h-8 px-2 text-xs text-muted hover:text-ink underline decoration-ink/20 underline-offset-2 outline-none interactive-focus rounded-sm"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          <p className="text-xs text-muted font-sans">
            Same order as the public events page (soonest first). The # labels give a
            listing&apos;s place on /events; hidden listings never appear there. Edit locks
            the listing; delete removes it from the site.
          </p>
          {eventsError ? (
            <p role="alert" className="text-xs text-deep-coral font-sans">
              Live events didn&apos;t load: {eventsError}. Refresh to try again.
            </p>
          ) : liveEvents.length === 0 ? (
            <div className="border border-ink/10 border-dashed rounded-xl p-12 text-center bg-canvas">
              <h3 className="font-display text-base font-semibold text-ink">
                No live events right now
              </h3>
              <p className="text-xs text-muted mt-1 font-sans">
                Synced Instagram listings will appear here when active.
              </p>
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="border border-ink/10 border-dashed rounded-xl p-12 text-center bg-canvas">
              <h3 className="font-display text-base font-semibold text-ink">
                No matching events
              </h3>
              <p className="text-xs text-muted mt-1 font-sans max-w-[48ch] mx-auto">
                Only upcoming listings are here, so a post for an event that has
                already ended won&apos;t match. Try another search or clear the filters.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredEvents.map((evt) => (
                <AdminLiveEventRow
                  key={evt.id}
                  event={evt}
                  feedIndex={feedPositionById.get(evt.id) ?? null}
                  isActionPending={isEventActionPending(pendingAction, evt.id)}
                  error={actionErrorFor(actionError, ["delete"], evt.id)}
                  onEdit={() => setEditingEventId(evt.id)}
                  onDelete={() => handleDelete(evt)}
                />
              ))}
            </div>
          )}
        </section>
      </main>

      {editingEvent && (
        <AdminEventEditDrawer
          key={editingEvent.id}
          event={editingEvent}
          isPending={isEventUpdatePending(pendingAction, editingEvent.id)}
          error={actionErrorFor(actionError, ["update"], editingEvent.id)}
          onClose={() => setEditingEventId(null)}
          onSave={handleSave}
          onInvalid={(message) =>
            setActionError({
              action: { type: "update", id: editingEvent.id },
              message,
            })
          }
        />
      )}

      <div
        className="pointer-events-none fixed bottom-4 right-4 z-[60]"
        role="status"
        aria-live="polite"
      >
        {pendingAction && (
          <div className="bg-ink text-canvas text-xs font-sans px-3 py-2 rounded-md shadow-card flex items-center gap-2">
            <svg className="motion-safe:animate-spin h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" aria-hidden>
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            Saving…
          </div>
        )}
      </div>
    </div>
  );
}
