"use client";

import React, { useMemo, useState } from "react";
import {
  logoutAdmin,
  updateEvent,
  deleteEvent,
  mergeDuplicateEvents,
  markEventsDifferent,
} from "../actions";
import { useRouter } from "next/navigation";
import { IoLogOut, IoOpenOutline, IoSearch } from "react-icons/io5";
import Link from "next/link";
import { formatDayShort, formatTimeParts } from "@/lib/dates";
import { AdminLiveEventRow } from "../AdminLiveEventRow";
import { AdminEventEditDrawer } from "../AdminEventEditDrawer";
import { AdminDuplicateReview } from "../AdminDuplicateReview";
import { useAdminEventEdit } from "../useAdminEventEdit";
import { useAdminActions } from "../useAdminActions";
import {
  isEventActionPending,
  isEventUpdatePending,
} from "../pending-action";
import {
  type AdminEventRow,
  type DuplicateReviewPair,
  sortEventsByFeedOrder,
  matchesAdminSearch,
} from "../types";

interface AdminDashboardClientProps {
  initialEvents: AdminEventRow[];
  duplicatePairs: DuplicateReviewPair[];
  duplicateQueueError: string | null;
}

function formatAdminEventDate(isoStr: string) {
  try {
    const { time, period } = formatTimeParts(isoStr);
    return `${formatDayShort(isoStr)}, ${time} ${period}`.trim();
  } catch {
    return isoStr;
  }
}

export default function AdminDashboardClient({
  initialEvents,
  duplicatePairs,
  duplicateQueueError,
}: AdminDashboardClientProps) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [editingEventId, setEditingEventId] = useState<string | null>(null);
  const { pendingAction, actionError, setActionError, runAction } =
    useAdminActions();

  const editingEvent = useMemo(
    () => initialEvents.find((e) => e.id === editingEventId) ?? null,
    [initialEvents, editingEventId]
  );
  const { form, setField, buildUpdatePayload } = useAdminEventEdit(editingEvent);

  const handleLogout = () => {
    void runAction({ type: "logout" }, async () => {
      await logoutAdmin();
      router.push("/admin/login");
      router.refresh();
    });
  };

  const startEditing = (event: AdminEventRow) => {
    setEditingEventId(event.id);
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingEventId) return;

    const built = buildUpdatePayload();
    if (!built.ok) {
      setActionError(built.error);
      return;
    }

    const eventId = editingEventId;
    void runAction({ type: "update", id: eventId }, async () => {
      const res = await updateEvent(eventId, built.payload);
      if (res.success) {
        setEditingEventId(null);
        router.refresh();
      } else {
        setActionError(res.error || "Failed to update event.");
      }
    });
  };

  const handleDelete = (id: string) => {
    if (
      !confirm(
        "Delete this event from the public calendar? This cannot be undone."
      )
    )
      return;
    void runAction({ type: "delete", id }, async () => {
      const res = await deleteEvent(id);
      if (res.success) {
        router.refresh();
      } else {
        setActionError(res.error || "Failed to delete event.");
      }
    });
  };

  const handleMerge = (
    pairKey: string,
    kept: AdminEventRow,
    removed: AdminEventRow
  ) => {
    void runAction({ type: "merge", id: pairKey }, async () => {
      const res = await mergeDuplicateEvents(kept.id, removed.id, {
        kept: kept.updated_at,
        removed: removed.updated_at,
      });
      if (res.success) {
        router.refresh();
      } else {
        setActionError(res.error || "Failed to merge events.");
      }
    });
  };

  const handleDistinct = (pairKey: string, pair: DuplicateReviewPair) => {
    void runAction({ type: "distinct", id: pairKey }, async () => {
      const res = await markEventsDifferent(pair.first.id, pair.second.id);
      if (res.success) {
        router.refresh();
      } else {
        setActionError(res.error || "Failed to save the decision.");
      }
    });
  };

  const eventsInFeedOrder = sortEventsByFeedOrder(initialEvents);
  const feedPositionById = new Map(
    eventsInFeedOrder.map((event, index) => [event.id, index])
  );

  const filteredEvents = eventsInFeedOrder.filter((e) =>
    matchesAdminSearch(search, e.title, e.host, e.location, e.description)
  );

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
            <p className="text-[11px] text-muted font-sans truncate sm:max-w-none">
              Manage live events
            </p>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <Link
              href="/events"
              target="_blank"
              className="flex items-center gap-1.5 text-xs text-muted hover:text-ink transition-colors font-sans py-2 px-2.5 sm:px-3 hover:bg-surface border border-transparent hover:border-ink/5 rounded-md outline-none interactive-focus"
            >
              <IoOpenOutline size={15} aria-hidden />
              <span className="hidden sm:inline">View site</span>
            </Link>
            <button
              onClick={handleLogout}
              disabled={pendingAction?.type === "logout"}
              className="flex items-center gap-1.5 text-xs text-muted hover:text-ink transition-colors font-sans py-2 px-2.5 sm:px-3 hover:bg-surface border border-transparent hover:border-ink/5 rounded-md outline-none interactive-focus disabled:opacity-50"
            >
              <IoLogOut size={15} aria-hidden />
              <span>Sign out</span>
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 w-full max-w-6xl mx-auto p-4 sm:p-6 space-y-6">
        {actionError && (
          <div
            role="alert"
            className="p-4 bg-coral/10 border border-deep-coral/20 text-deep-coral rounded-md text-sm font-sans flex items-start gap-2 animate-field-reveal"
          >
            <span aria-hidden>⚠️</span>
            <p className="flex-1 font-sans">{actionError}</p>
            <button
              type="button"
              onClick={() => setActionError(null)}
              className="text-deep-coral hover:text-ink transition-colors outline-none font-bold"
              aria-label="Dismiss error"
            >
              ×
            </button>
          </div>
        )}

        <AdminDuplicateReview
          pairs={duplicatePairs}
          queueError={duplicateQueueError}
          feedPositionById={feedPositionById}
          pendingAction={pendingAction}
          onMerge={handleMerge}
          onDistinct={handleDistinct}
        />

        <div className="space-y-3 border-b border-ink/10 pb-3 pt-4">
          <div className="flex items-baseline justify-between gap-4">
            <h2 className="font-display text-base font-semibold text-ink">
              Live events
            </h2>
            <p className="text-[11px] text-muted">
              {initialEvents.length} on the public calendar
            </p>
          </div>

          <div className="relative max-w-md">
            <IoSearch
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted/50 pointer-events-none"
              size={14}
              aria-hidden
            />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by title, host, or location…"
              className="w-full bg-canvas border border-ink/15 rounded-md pl-9 pr-3 py-2 text-sm placeholder:text-muted/40 transition-colors focus:border-ink outline-none interactive-focus"
            />
          </div>
        </div>

        <div className="space-y-4 animate-fade-up">
          <p className="text-xs text-muted font-sans">
            Same order as the public events page (soonest first). Flyer thumbnails match what
            students see — use the # labels to find a row on /events. Edit locks the listing;
            delete removes it from the site.
          </p>
          {initialEvents.length === 0 ? (
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
              <span className="text-2xl" aria-hidden>
                🔍
              </span>
              <h3 className="font-display text-base font-semibold mt-2 text-ink">
                No matching events
              </h3>
              <p className="text-xs text-muted mt-1 font-sans">
                Try a different search term or clear the search box.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredEvents.map((evt) => (
                <AdminLiveEventRow
                  key={evt.id}
                  event={evt}
                  feedIndex={feedPositionById.get(evt.id) ?? 0}
                  formatDate={formatAdminEventDate}
                  isActionPending={isEventActionPending(pendingAction, evt.id)}
                  onEdit={() => startEditing(evt)}
                  onDelete={() => handleDelete(evt.id)}
                />
              ))}
            </div>
          )}
        </div>
      </main>

      {editingEventId && (
        <AdminEventEditDrawer
          form={form}
          setField={setField}
          onClose={() => setEditingEventId(null)}
          onSubmit={handleUpdate}
          isPending={
            editingEventId
              ? isEventUpdatePending(pendingAction, editingEventId)
              : false
          }
        />
      )}

      {pendingAction && (
        <div
          className="fixed bottom-4 right-4 z-[60] bg-ink text-canvas text-xs font-sans px-3 py-2 rounded-md shadow-card flex items-center gap-2"
          role="status"
          aria-live="polite"
        >
          <svg className="animate-spin h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" aria-hidden>
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
  );
}
