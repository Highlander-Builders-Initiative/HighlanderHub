"use client";

import React, { useState, useMemo } from "react";
import {
  logoutAdmin,
  approveSubmission,
  rejectSubmission,
  updateEvent,
  deleteEvent,
} from "../actions";
import { useRouter } from "next/navigation";
import { IoLogOut, IoOpenOutline, IoSearch } from "react-icons/io5";
import Link from "next/link";
import { formatDayShort, formatTimeParts } from "@/lib/dates";
import { AdminSubmissionCard } from "../AdminSubmissionCard";
import { AdminLiveEventRow } from "../AdminLiveEventRow";
import { AdminEventEditDrawer } from "../AdminEventEditDrawer";
import { AdminRejectDialog } from "../AdminRejectDialog";
import { useAdminEventEdit } from "../useAdminEventEdit";
import { useAdminActions } from "../useAdminActions";
import {
  isEventActionPending,
  isEventUpdatePending,
  isRejectDialogPending,
  isSubmissionActionPending,
} from "../pending-action";
import {
  type SubmissionRow,
  type AdminEventRow,
  sortEventsByFeedOrder,
  matchesAdminSearch,
} from "../types";

type AdminTab = "submissions" | "events";

interface AdminDashboardClientProps {
  initialSubmissions: SubmissionRow[];
  initialEvents: AdminEventRow[];
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
  initialSubmissions,
  initialEvents,
}: AdminDashboardClientProps) {
  const router = useRouter();
  const pendingCount = initialSubmissions.length;
  const [activeTab, setActiveTab] = useState<AdminTab>(
    pendingCount > 0 ? "submissions" : "events"
  );
  const [searchByTab, setSearchByTab] = useState<Record<AdminTab, string>>({
    submissions: "",
    events: "",
  });
  const [editingEventId, setEditingEventId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [expandedSubmissionIds, setExpandedSubmissionIds] = useState<Set<string>>(
    () => new Set()
  );
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

  const handleApprove = (id: string) => {
    if (
      !confirm(
        "Approve this submission? It will appear on the public events calendar immediately."
      )
    )
      return;
    void runAction({ type: "approve", id }, async () => {
      const res = await approveSubmission(id);
      if (res.success) {
        router.refresh();
      } else {
        setActionError(res.error || "Failed to approve submission.");
      }
    });
  };

  const openRejectModal = (id: string) => {
    setRejectingId(id);
    setRejectReason("");
    setActionError(null);
  };

  const closeRejectModal = () => {
    setRejectingId(null);
    setRejectReason("");
  };

  const handleRejectConfirm = () => {
    if (!rejectingId) return;
    const id = rejectingId;
    void runAction({ type: "reject", id }, async () => {
      const res = await rejectSubmission(id, rejectReason.trim());
      if (res.success) {
        closeRejectModal();
        router.refresh();
      } else {
        setActionError(res.error || "Failed to reject submission.");
      }
    });
  };

  const toggleSubmissionDescription = (id: string) => {
    setExpandedSubmissionIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
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

  const activeSearch = searchByTab[activeTab];

  const filteredSubmissions = initialSubmissions.filter((sub) =>
    matchesAdminSearch(
      searchByTab.submissions,
      sub.title,
      sub.host,
      sub.location,
      sub.submitter_name,
      sub.submitter_email,
      sub.submitter_org
    )
  );

  const eventsInFeedOrder = sortEventsByFeedOrder(initialEvents);
  const feedPositionById = new Map(
    eventsInFeedOrder.map((event, index) => [event.id, index])
  );

  const filteredEvents = eventsInFeedOrder.filter((e) =>
    matchesAdminSearch(
      searchByTab.events,
      e.title,
      e.host,
      e.location,
      e.description
    )
  );

  const rejectingSubmission = rejectingId
    ? initialSubmissions.find((s) => s.id === rejectingId)
    : null;

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
              Review submissions and manage live events
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

        <section className="grid grid-cols-2 gap-3" aria-label="Admin overview">
          <button
            type="button"
            onClick={() => setActiveTab("submissions")}
            className={`text-left rounded-xl border p-4 transition-all outline-none interactive-focus ${
              activeTab === "submissions"
                ? "border-deep-coral/30 bg-coral/5 shadow-card"
                : "border-ink/10 bg-canvas hover:border-ink/20"
            }`}
          >
            <p className="text-[11px] font-sans text-muted">Awaiting review</p>
            <p className="font-display text-2xl font-semibold text-ink mt-1 tabular-nums">
              {pendingCount}
            </p>
            <p className="text-[11px] text-muted font-sans mt-1">
              {pendingCount === 1 ? "submission" : "submissions"} to approve
            </p>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("events")}
            className={`text-left rounded-xl border p-4 transition-all outline-none interactive-focus ${
              activeTab === "events"
                ? "border-ink/25 bg-ink/[0.03] shadow-card"
                : "border-ink/10 bg-canvas hover:border-ink/20"
            }`}
          >
            <p className="text-[11px] font-sans text-muted">On public calendar</p>
            <p className="font-display text-2xl font-semibold text-ink mt-1 tabular-nums">
              {initialEvents.length}
            </p>
            <p className="text-[11px] text-muted font-sans mt-1">live events</p>
          </button>
        </section>

        {pendingCount > 0 && activeTab === "submissions" && (
          <div className="rounded-lg border border-deep-coral/15 bg-coral/5 px-4 py-3 text-sm font-sans text-ink">
            <strong className="font-semibold">{pendingCount}</strong>{" "}
            {pendingCount === 1 ? "submission needs" : "submissions need"} your review.
            Approve to publish on the public feed, or reject with an optional note for your records.
          </div>
        )}

        <div className="space-y-3 border-b border-ink/10 pb-3">
          <nav className="flex gap-4 sm:gap-6 overflow-x-auto" role="tablist" aria-label="Admin sections">
            <button
              type="button"
              role="tab"
              id="tab-submissions"
              aria-controls="panel-submissions"
              onClick={() => setActiveTab("submissions")}
              aria-selected={activeTab === "submissions"}
              className="tab whitespace-nowrap shrink-0"
            >
              Review queue
              {pendingCount > 0 && (
                <span className="ml-2 font-mono text-[10px] bg-coral/10 text-deep-coral px-1.5 py-0.5 rounded-full font-semibold border border-deep-coral/10">
                  {pendingCount}
                </span>
              )}
            </button>
            <button
              type="button"
              role="tab"
              id="tab-events"
              aria-controls="panel-events"
              onClick={() => setActiveTab("events")}
              aria-selected={activeTab === "events"}
              className="tab whitespace-nowrap shrink-0"
            >
              Live events
              <span className="ml-2 font-mono text-[10px] bg-ink/5 text-muted px-1.5 py-0.5 rounded-full border border-ink/10">
                {initialEvents.length}
              </span>
            </button>
          </nav>

          <div className="relative max-w-md">
            <IoSearch
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted/50 pointer-events-none"
              size={14}
              aria-hidden
            />
            <input
              type="search"
              value={activeSearch}
              onChange={(e) =>
                setSearchByTab((prev) => ({ ...prev, [activeTab]: e.target.value }))
              }
              placeholder={
                activeTab === "submissions"
                  ? "Search by title, host, or submitter…"
                  : "Search by title, host, or location…"
              }
              className="w-full bg-canvas border border-ink/15 rounded-md pl-9 pr-3 py-2 text-sm placeholder:text-muted/40 transition-colors focus:border-ink outline-none interactive-focus"
            />
          </div>
        </div>

        {activeTab === "submissions" && (
          <div
            id="panel-submissions"
            role="tabpanel"
            aria-labelledby="tab-submissions"
            className="space-y-6 animate-fade-up"
          >
            {pendingCount === 0 ? (
              <div className="border border-ink/10 border-dashed rounded-xl p-12 text-center bg-canvas">
                <span className="text-2xl" aria-hidden>
                  ✓
                </span>
                <h3 className="font-display text-base font-semibold mt-2 text-ink">
                  Review queue is empty
                </h3>
                <p className="text-xs text-muted mt-1 max-w-sm mx-auto font-sans">
                  No community submissions are waiting. Switch to Live events to edit or remove
                  published listings.
                </p>
                <button
                  type="button"
                  onClick={() => setActiveTab("events")}
                  className="mt-4 text-xs font-semibold text-ink underline underline-offset-2 hover:no-underline outline-none interactive-focus"
                >
                  Go to live events
                </button>
              </div>
            ) : filteredSubmissions.length === 0 ? (
              <div className="border border-ink/10 border-dashed rounded-xl p-12 text-center bg-canvas">
                <span className="text-2xl" aria-hidden>
                  🔍
                </span>
                <h3 className="font-display text-base font-semibold mt-2 text-ink">
                  No matching submissions
                </h3>
                <p className="text-xs text-muted mt-1 font-sans">
                  Try a different search term or clear the search box.
                </p>
              </div>
            ) : (
              <div className="grid gap-6 md:grid-cols-2">
                {filteredSubmissions.map((sub) => (
                  <AdminSubmissionCard
                    key={sub.id}
                    submission={sub}
                    formatDate={formatAdminEventDate}
                    isExpanded={expandedSubmissionIds.has(sub.id)}
                    onToggleDescription={() => toggleSubmissionDescription(sub.id)}
                    onApprove={() => handleApprove(sub.id)}
                    onReject={() => openRejectModal(sub.id)}
                    disabled={isSubmissionActionPending(pendingAction, sub.id)}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === "events" && (
          <div
            id="panel-events"
            role="tabpanel"
            aria-labelledby="tab-events"
            className="space-y-4 animate-fade-up"
          >
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
                  Approved submissions and synced sources will appear here when active.
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
        )}
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

      {rejectingId && rejectingSubmission && (
        <AdminRejectDialog
          title={rejectingSubmission.title}
          reason={rejectReason}
          onReasonChange={setRejectReason}
          onCancel={closeRejectModal}
          onConfirm={handleRejectConfirm}
          isPending={isRejectDialogPending(pendingAction, rejectingId)}
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
