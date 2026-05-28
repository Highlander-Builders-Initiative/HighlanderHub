"use client";

import React, { useState, useTransition } from "react";
import {
  logoutAdmin,
  approveSubmission,
  rejectSubmission,
  updateEvent,
  deleteEvent,
} from "../actions";
import { useRouter } from "next/navigation";
import {
  IoCheckmark,
  IoClose,
  IoPencil,
  IoTrash,
  IoLogOut,
  IoCalendar,
  IoLocation,
  IoPerson,
  IoLink,
  IoSearch,
  IoMailOutline,
  IoOpenOutline,
  IoChevronDown,
  IoChevronUp,
} from "react-icons/io5";
import Link from "next/link";
import { formatDayShort, formatTimeParts } from "@/lib/dates";
import { CATEGORY_RAIL } from "@/lib/category-colors";
import type { CampusEvent } from "@/types/event";

interface SubmissionRow {
  id: string;
  title: string;
  description: string;
  starts_at: string;
  ends_at: string | null;
  location: string;
  host: string;
  host_handle: string | null;
  category: string;
  tags: string[];
  source_url: string | null;
  image_url: string | null;
  is_free: boolean;
  rsvp_required: boolean;
  rsvp_url: string | null;
  submitter_name: string;
  submitter_email: string;
  submitter_org: string | null;
  status: "pending" | "approved" | "rejected";
  created_at: string;
}

interface EventRow {
  id: string;
  title: string;
  description: string;
  starts_at: string;
  ends_at: string | null;
  location: string;
  host: string;
  host_handle: string | null;
  category: string;
  tags: string[];
  source: string;
  source_url: string | null;
  image_url: string | null;
  is_free: boolean;
  rsvp_required: boolean;
  rsvp_url: string | null;
  is_locked: boolean;
  created_at: string;
}

interface AdminDashboardClientProps {
  initialSubmissions: SubmissionRow[];
  initialEvents: EventRow[];
}

/** Same ordering as `getEventsPage` on the public /events feed. */
function sortEventsByFeedOrder(events: EventRow[]): EventRow[] {
  return [...events].sort((a, b) => {
    const byStart = a.starts_at.localeCompare(b.starts_at);
    if (byStart !== 0) return byStart;
    return a.id.localeCompare(b.id);
  });
}

function AdminLiveEventRow({
  event,
  feedIndex,
  formatDate,
  onEdit,
  onDelete,
  disabled,
}: {
  event: EventRow;
  feedIndex: number;
  formatDate: (iso: string) => string;
  onEdit: () => void;
  onDelete: () => void;
  disabled: boolean;
}) {
  const [imageBroken, setImageBroken] = useState(false);
  const showImage = Boolean(event.image_url) && !imageBroken;
  const { time, period } = formatTimeParts(event.starts_at);
  const rail =
    CATEGORY_RAIL[event.category as CampusEvent["category"]] ?? "bg-ink";

  return (
    <article className="bg-canvas border border-ink/10 rounded-xl shadow-card hover:border-ink/25 transition-all overflow-hidden flex flex-col sm:flex-row sm:items-stretch">
      <div className="flex flex-1 min-w-0 min-h-[6rem]">
        <div className="relative flex shrink-0 flex-col items-center justify-center w-16 sm:w-[68px] px-2">
          <span
            aria-hidden
            className={`pointer-events-none absolute bottom-0 right-0 top-0 w-[2px] ${rail}`}
          />
          <span className="font-mono text-[10px] text-muted tabular-nums">#{feedIndex + 1}</span>
          <span className="font-mono font-medium leading-none text-ink tabular-nums text-[22px] mt-1">
            {time}
          </span>
          {period && (
            <span className="mt-1.5 font-mono font-medium uppercase text-muted text-[10px] tracking-[0.14em]">
              {period}
            </span>
          )}
        </div>

        {showImage ? (
          <div className="relative shrink-0 self-stretch py-2 pl-2">
            <div className="relative h-full w-[80px] min-h-[4.5rem] overflow-hidden rounded-md bg-surface">
              <img
                src={event.image_url!}
                alt={`${event.title} flyer`}
                className="absolute inset-0 h-full w-full object-cover"
                onError={() => setImageBroken(true)}
              />
              <span
                aria-hidden
                className="pointer-events-none absolute inset-0 rounded-md ring-1 ring-inset ring-ink/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.45)]"
              />
            </div>
          </div>
        ) : (
          <div className="relative shrink-0 self-stretch py-2 pl-2">
            <div
              className="flex h-full w-[80px] min-h-[4.5rem] items-center justify-center rounded-md border border-dashed border-ink/15 bg-surface text-[9px] font-sans text-muted text-center px-1 leading-tight"
              aria-label="No flyer image"
            >
              No flyer
            </div>
          </div>
        )}

        <div className="min-w-0 flex-1 py-3 pr-3 pl-3 sm:pl-4">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="bg-ink/5 border border-ink/10 text-muted font-mono text-[9px] px-1 py-0.5 rounded font-semibold uppercase">
              {event.source}
            </span>
            <span className="font-mono text-[10px] text-muted">{formatDate(event.starts_at)}</span>
            {event.is_locked && (
              <span className="bg-gold/10 border border-gold/20 text-deep-gold font-mono text-[9px] px-1 py-0.5 rounded font-semibold tracking-wider">
                Locked
              </span>
            )}
          </div>
          <h4 className="font-display text-sm font-semibold text-ink leading-snug">{event.title}</h4>
          <p className="text-xs text-muted font-sans mt-1 line-clamp-2">
            {event.location} · {event.host}
          </p>
          {event.description && (
            <p className="text-xs text-muted/80 font-sans mt-1 line-clamp-1">{event.description}</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 border-t sm:border-t-0 sm:border-l border-ink/10 p-3 sm:p-4 sm:flex-col sm:justify-center shrink-0">
        <button
          type="button"
          onClick={onEdit}
          disabled={disabled}
          className="flex-1 sm:flex-none min-h-9 px-3 border border-ink/10 hover:bg-ink/5 text-muted hover:text-ink rounded-md transition-all outline-none interactive-focus flex items-center justify-center gap-1.5 text-xs font-semibold disabled:opacity-50"
        >
          <IoPencil size={14} aria-hidden />
          <span>Edit</span>
        </button>
        <button
          type="button"
          onClick={onDelete}
          disabled={disabled}
          className="flex-1 sm:flex-none min-h-9 px-3 border border-coral/20 hover:bg-coral/5 text-muted hover:text-deep-coral rounded-md transition-all outline-none interactive-focus flex items-center justify-center gap-1.5 text-xs font-semibold disabled:opacity-50"
        >
          <IoTrash size={14} aria-hidden />
          <span>Delete</span>
        </button>
      </div>
    </article>
  );
}

export default function AdminDashboardClient({
  initialSubmissions,
  initialEvents,
}: AdminDashboardClientProps) {
  const router = useRouter();
  const pendingCount = initialSubmissions.length;
  const [activeTab, setActiveTab] = useState<"submissions" | "events">(
    pendingCount > 0 ? "submissions" : "events"
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [submissionSearch, setSubmissionSearch] = useState("");
  const [editingEventId, setEditingEventId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [expandedSubmissionIds, setExpandedSubmissionIds] = useState<Set<string>>(
    () => new Set()
  );
  const [isPending, startTransition] = useTransition();
  const [actionError, setActionError] = useState<string | null>(null);

  // Editing form states
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editStartsAt, setEditStartsAt] = useState("");
  const [editEndsAt, setEditEndsAt] = useState("");
  const [editLocation, setEditLocation] = useState("");
  const [editHost, setEditHost] = useState("");
  const [editHostHandle, setEditHostHandle] = useState("");
  const [editCategory, setEditCategory] = useState("");
  const [editImageUrl, setEditImageUrl] = useState("");
  const [editRsvpUrl, setEditRsvpUrl] = useState("");
  const [editIsFree, setEditIsFree] = useState(true);
  const [editRsvpRequired, setEditRsvpRequired] = useState(false);

  // Pacific campus time; composed from shared Intl formatters so SSR and browser match.
  const formatDate = (isoStr: string) => {
    try {
      const { time, period } = formatTimeParts(isoStr);
      return `${formatDayShort(isoStr)}, ${time} ${period}`.trim();
    } catch {
      return isoStr;
    }
  };

  // Convert HTML local datetime-local format to ISO
  const formatLocalToISO = (localStr: string) => {
    if (!localStr) return "";
    return new Date(localStr).toISOString();
  };

  // Convert ISO string back to datetime-local local format for input tags
  const formatISOToLocal = (isoStr: string | null) => {
    if (!isoStr) return "";
    try {
      const date = new Date(isoStr);
      const tzOffset = date.getTimezoneOffset() * 60000;
      const localISOTime = new Date(date.getTime() - tzOffset)
        .toISOString()
        .slice(0, 16);
      return localISOTime;
    } catch {
      return "";
    }
  };

  const handleLogout = () => {
    startTransition(async () => {
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
    setActionError(null);
    startTransition(async () => {
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
    setActionError(null);
    startTransition(async () => {
      const res = await rejectSubmission(rejectingId, rejectReason.trim());
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

  const startEditing = (event: EventRow) => {
    setEditingEventId(event.id);
    setEditTitle(event.title);
    setEditDescription(event.description || "");
    setEditStartsAt(formatISOToLocal(event.starts_at));
    setEditEndsAt(formatISOToLocal(event.ends_at));
    setEditLocation(event.location);
    setEditHost(event.host);
    setEditHostHandle(event.host_handle || "");
    setEditCategory(event.category);
    setEditImageUrl(event.image_url || "");
    setEditRsvpUrl(event.rsvp_url || "");
    setEditIsFree(event.is_free);
    setEditRsvpRequired(event.rsvp_required);
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingEventId) return;

    setActionError(null);
    startTransition(async () => {
      const payload = {
        title: editTitle,
        description: editDescription,
        starts_at: formatLocalToISO(editStartsAt),
        ends_at: editEndsAt ? formatLocalToISO(editEndsAt) : null,
        location: editLocation,
        host: editHost,
        host_handle: editHostHandle || null,
        category: editCategory,
        image_url: editImageUrl || null,
        rsvp_url: editRsvpUrl || null,
        is_free: editIsFree,
        rsvp_required: editRsvpRequired,
      };

      const res = await updateEvent(editingEventId, payload);
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
    setActionError(null);
    startTransition(async () => {
      const res = await deleteEvent(id);
      if (res.success) {
        router.refresh();
      } else {
        setActionError(res.error || "Failed to delete event.");
      }
    });
  };

  const matchesQuery = (query: string, ...fields: (string | null | undefined)[]) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return fields.some((f) => f?.toLowerCase().includes(q));
  };

  const filteredSubmissions = initialSubmissions.filter((sub) =>
    matchesQuery(
      submissionSearch,
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
    matchesQuery(searchQuery, e.title, e.host, e.location, e.description)
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
              disabled={isPending}
              className="flex items-center gap-1.5 text-xs text-muted hover:text-ink transition-colors font-sans py-2 px-2.5 sm:px-3 hover:bg-surface border border-transparent hover:border-ink/5 rounded-md outline-none interactive-focus"
            >
              <IoLogOut size={15} aria-hidden />
              <span>Sign out</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Admin Content Area */}
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

        {/* Overview */}
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

        {/* Tabs + search */}
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
              value={activeTab === "submissions" ? submissionSearch : searchQuery}
              onChange={(e) =>
                activeTab === "submissions"
                  ? setSubmissionSearch(e.target.value)
                  : setSearchQuery(e.target.value)
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

        {/* Tab content 1: Submissions */}
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
                  <div
                    key={sub.id}
                    className="bg-canvas border border-ink/10 rounded-xl p-5 shadow-card hover:border-ink/20 transition-all flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-3 border-b border-ink/5 pb-3 mb-4">
                        <div className="min-w-0 space-y-1">
                          <p className="text-[11px] font-sans text-muted">
                            Submitted by{" "}
                            <strong className="text-ink font-semibold">{sub.submitter_name}</strong>
                            {sub.submitter_org && (
                              <span className="text-muted"> · {sub.submitter_org}</span>
                            )}
                          </p>
                          <a
                            href={`mailto:${sub.submitter_email}`}
                            className="inline-flex items-center gap-1 text-[11px] text-muted hover:text-ink font-sans truncate max-w-full"
                          >
                            <IoMailOutline size={12} aria-hidden />
                            {sub.submitter_email}
                          </a>
                        </div>
                        <time
                          dateTime={sub.created_at}
                          className="font-mono text-[9px] text-muted shrink-0 text-right"
                        >
                          {formatDate(sub.created_at)}
                        </time>
                      </div>

                      {/* Event details */}
                      <div className="space-y-4">
                        <div>
                          <div className="flex items-center gap-1.5 mb-1 select-none">
                            <span
                              className={`h-1.5 w-1.5 rounded-full ${
                                sub.category === "club"
                                  ? "bg-highlander"
                                  : sub.category === "academic" || sub.category === "community"
                                  ? "bg-leaf"
                                  : sub.category === "social" || sub.category === "arts"
                                  ? "bg-coral"
                                  : sub.category === "free_food"
                                  ? "bg-gold"
                                  : "bg-ink"
                              }`}
                            />
                            <span className="text-[10px] font-mono uppercase tracking-wider text-muted">
                              {sub.category.replace("_", " ")}
                            </span>
                            {sub.is_free && (
                              <span className="bg-leaf/10 text-deep-leaf text-[9px] px-1 py-0.2 rounded font-mono font-semibold">
                                FREE
                              </span>
                            )}
                          </div>
                          <h3 className="font-display text-base font-semibold text-ink leading-snug">
                            {sub.title}
                          </h3>
                        </div>

                        {/* Flyer image if exists */}
                        {sub.image_url && (
                          <div className="relative border border-ink/10 rounded-lg overflow-hidden max-h-[220px] bg-surface flex justify-center group select-none">
                            <img
                              src={sub.image_url}
                              alt="Flyer image"
                              className="object-contain max-h-[220px] hover:scale-[1.02] transition-transform duration-200"
                              onError={(e) => {
                                // hide broken image container or handle elegantly
                                (e.target as HTMLElement).style.display = "none";
                              }}
                            />
                          </div>
                        )}

                        <div>
                          <p
                            className={`text-xs text-muted font-sans leading-relaxed whitespace-pre-line ${
                              expandedSubmissionIds.has(sub.id) ? "" : "line-clamp-4"
                            }`}
                          >
                            {sub.description}
                          </p>
                          {sub.description.length > 200 && (
                            <button
                              type="button"
                              onClick={() => toggleSubmissionDescription(sub.id)}
                              className="mt-1.5 inline-flex items-center gap-0.5 text-[11px] font-semibold text-ink hover:underline outline-none interactive-focus"
                            >
                              {expandedSubmissionIds.has(sub.id) ? (
                                <>
                                  Show less <IoChevronUp size={12} aria-hidden />
                                </>
                              ) : (
                                <>
                                  Show full description <IoChevronDown size={12} aria-hidden />
                                </>
                              )}
                            </button>
                          )}
                        </div>

                        <div className="grid gap-2 border-t border-ink/5 pt-3 select-none">
                          <div className="flex items-center gap-2 text-[11px] text-muted font-sans">
                            <IoCalendar className="text-ink/40" size={13} />
                            <span className="font-mono">
                              {formatDate(sub.starts_at)}
                              {sub.ends_at && ` - ${formatDate(sub.ends_at)}`}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-[11px] text-muted font-sans">
                            <IoLocation className="text-ink/40" size={13} />
                            <span>{sub.location}</span>
                          </div>
                          <div className="flex items-center gap-2 text-[11px] text-muted font-sans">
                            <IoPerson className="text-ink/40" size={13} />
                            <span>{sub.host}</span>
                          </div>
                          {sub.rsvp_url && (
                            <div className="flex items-center gap-2 text-[11px] text-muted font-sans">
                              <IoLink className="text-ink/40" size={13} />
                              <a
                                href={sub.rsvp_url}
                                target="_blank"
                                rel="noreferrer"
                                className="underline hover:text-ink font-mono truncate"
                              >
                                {sub.rsvp_url}
                              </a>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 border-t border-ink/10 pt-4 mt-4">
                      <button
                        type="button"
                        onClick={() => handleApprove(sub.id)}
                        disabled={isPending}
                        className="flex-1 min-h-10 bg-ink hover:bg-ink/90 active:scale-[0.99] text-canvas text-xs font-semibold rounded-md flex items-center justify-center gap-1.5 transition-all outline-none interactive-focus disabled:opacity-50"
                      >
                        <IoCheckmark size={15} aria-hidden />
                        <span>Approve & publish</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => openRejectModal(sub.id)}
                        disabled={isPending}
                        className="min-h-10 px-4 border border-coral/30 hover:bg-coral/5 text-deep-coral text-xs font-semibold rounded-md flex items-center justify-center gap-1.5 transition-all outline-none interactive-focus disabled:opacity-50"
                      >
                        <IoClose size={15} aria-hidden />
                        <span>Reject</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab content 2: Live Events */}
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
                    formatDate={formatDate}
                    disabled={isPending}
                    onEdit={() => startEditing(evt)}
                    onDelete={() => handleDelete(evt.id)}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Slide-out Edit Drawer (or bottom sheet overlay) */}
      {editingEventId && (
        <div className="fixed inset-0 bg-ink/35 backdrop-blur-sm z-50 flex items-center justify-end animate-fade-in p-4 sm:p-0">
          <div className="bg-canvas w-full max-w-[540px] h-full sm:h-screen sm:rounded-l-xl border-l border-ink/10 p-6 sm:p-8 flex flex-col justify-between overflow-y-auto animate-scale-in">
            <form onSubmit={handleUpdate} className="space-y-6 flex-1 flex flex-col justify-between">
              <div>
                <header className="flex items-center justify-between border-b border-ink/10 pb-4 mb-6 select-none">
                  <div>
                    <h3 className="font-display text-lg font-semibold text-ink leading-tight">
                      Edit event
                    </h3>
                    <p className="text-[11px] font-sans text-muted mt-1 leading-normal">
                      Saving locks this listing so automated imports won&apos;t overwrite your
                      changes.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setEditingEventId(null)}
                    className="p-2 text-muted hover:text-ink transition-colors rounded-md outline-none interactive-focus"
                  >
                    <IoClose size={20} />
                  </button>
                </header>

                <div className="space-y-4">
                  {/* Title */}
                  <div className="space-y-1.5">
                    <label className="block text-[12px] font-sans text-muted">Event Title</label>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      required
                      className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors"
                    />
                  </div>

                  {/* Description */}
                  <div className="space-y-1.5">
                    <label className="block text-[12px] font-sans text-muted">Description</label>
                    <textarea
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      rows={4}
                      className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors resize-y font-sans leading-relaxed"
                    />
                  </div>

                  {/* StartsAt and EndsAt */}
                  <div className="grid grid-cols-2 gap-4 select-none">
                    <div className="space-y-1.5">
                      <label className="block text-[12px] font-sans text-muted">Starts At</label>
                      <input
                        type="datetime-local"
                        value={editStartsAt}
                        onChange={(e) => setEditStartsAt(e.target.value)}
                        required
                        className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors font-mono"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="block text-[12px] font-sans text-muted">Ends At (Optional)</label>
                      <input
                        type="datetime-local"
                        value={editEndsAt}
                        onChange={(e) => setEditEndsAt(e.target.value)}
                        className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors font-mono"
                      />
                    </div>
                  </div>

                  {/* Location & Host */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="block text-[12px] font-sans text-muted">Location</label>
                      <input
                        type="text"
                        value={editLocation}
                        onChange={(e) => setEditLocation(e.target.value)}
                        required
                        className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="block text-[12px] font-sans text-muted">Host Organizer</label>
                      <input
                        type="text"
                        value={editHost}
                        onChange={(e) => setEditHost(e.target.value)}
                        required
                        className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors"
                      />
                    </div>
                  </div>

                  {/* Category & Host handle */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="block text-[12px] font-sans text-muted">Category</label>
                      <select
                        value={editCategory}
                        onChange={(e) => setEditCategory(e.target.value)}
                        className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors"
                      >
                        <option value="club">Club</option>
                        <option value="academic">Academic</option>
                        <option value="social">Social</option>
                        <option value="career">Career</option>
                        <option value="sports">Sports</option>
                        <option value="arts">Arts</option>
                        <option value="community">Community</option>
                        <option value="free_food">Free Food</option>
                      </select>
                    </div>
                    <div className="space-y-1.5">
                      <label className="block text-[12px] font-sans text-muted">IG Handle (Optional)</label>
                      <input
                        type="text"
                        value={editHostHandle}
                        onChange={(e) => setEditHostHandle(e.target.value)}
                        placeholder="acm.ucr"
                        className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors font-mono"
                      />
                    </div>
                  </div>

                  {/* Image URL & RSVP URL */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="block text-[12px] font-sans text-muted">Flyer Image URL (Optional)</label>
                      <input
                        type="text"
                        value={editImageUrl}
                        onChange={(e) => setEditImageUrl(e.target.value)}
                        className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors font-mono"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="block text-[12px] font-sans text-muted">RSVP Link (Optional)</label>
                      <input
                        type="text"
                        value={editRsvpUrl}
                        onChange={(e) => setEditRsvpUrl(e.target.value)}
                        className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors font-mono"
                      />
                    </div>
                  </div>

                  {/* Toggles */}
                  <div className="grid grid-cols-2 gap-4 border-t border-ink/5 pt-4 select-none">
                    <label className="flex items-center gap-2 cursor-pointer font-sans text-sm text-ink">
                      <input
                        type="checkbox"
                        checked={editIsFree}
                        onChange={(e) => setEditIsFree(e.target.checked)}
                        className="h-4 w-4 accent-ink rounded text-ink outline-none interactive-focus"
                      />
                      <span>This event is FREE</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer font-sans text-sm text-ink">
                      <input
                        type="checkbox"
                        checked={editRsvpRequired}
                        onChange={(e) => setEditRsvpRequired(e.target.checked)}
                        className="h-4 w-4 accent-ink rounded text-ink outline-none interactive-focus"
                      />
                      <span>RSVP Required</span>
                    </label>
                  </div>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-3 border-t border-ink/10 pt-4 mt-6 select-none">
                <button
                  type="submit"
                  disabled={isPending}
                  className="flex-1 min-h-11 bg-ink hover:bg-ink/90 text-canvas text-xs font-semibold rounded-md transition-colors outline-none interactive-focus"
                >
                  Save changes
                </button>
                <button
                  type="button"
                  onClick={() => setEditingEventId(null)}
                  className="px-6 min-h-11 border border-ink/10 hover:bg-ink/5 text-muted hover:text-ink text-xs font-semibold rounded-md transition-colors outline-none interactive-focus"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reject submission modal */}
      {rejectingId && rejectingSubmission && (
        <div
          className="fixed inset-0 bg-ink/35 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in"
          role="dialog"
          aria-modal="true"
          aria-labelledby="reject-dialog-title"
        >
          <div className="bg-canvas w-full max-w-md rounded-xl border border-ink/10 p-6 shadow-card animate-scale-in">
            <header className="mb-4">
              <h3 id="reject-dialog-title" className="font-display text-lg font-semibold text-ink">
                Reject submission?
              </h3>
              <p className="text-xs text-muted font-sans mt-1">
                &ldquo;{rejectingSubmission.title}&rdquo; will not be published. You can add an
                internal note below (optional).
              </p>
            </header>
            <label className="block text-[12px] font-sans text-muted mb-1.5" htmlFor="reject-reason">
              Note (optional)
            </label>
            <textarea
              id="reject-reason"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              rows={3}
              placeholder="e.g. duplicate event, missing details…"
              className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors resize-y font-sans leading-relaxed mb-4"
            />
            <div className="flex flex-col-reverse sm:flex-row gap-2">
              <button
                type="button"
                onClick={closeRejectModal}
                disabled={isPending}
                className="flex-1 min-h-10 border border-ink/10 hover:bg-ink/5 text-muted hover:text-ink text-xs font-semibold rounded-md transition-colors outline-none interactive-focus"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRejectConfirm}
                disabled={isPending}
                className="flex-1 min-h-10 bg-deep-coral hover:bg-deep-coral/90 text-canvas text-xs font-semibold rounded-md transition-colors outline-none interactive-focus disabled:opacity-50"
              >
                Reject submission
              </button>
            </div>
          </div>
        </div>
      )}

      {isPending && (
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
