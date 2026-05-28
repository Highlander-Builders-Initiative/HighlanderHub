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
import { IoCheckmark, IoClose, IoPencil, IoTrash, IoLogOut, IoCalendar, IoLocation, IoPerson, IoLink, IoImage } from "react-icons/io5";
import { formatDayShort, formatTimeParts } from "@/lib/dates";

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

export default function AdminDashboardClient({
  initialSubmissions,
  initialEvents,
}: AdminDashboardClientProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"submissions" | "events">("submissions");
  const [searchQuery, setSearchQuery] = useState("");
  const [editingEventId, setEditingEventId] = useState<string | null>(null);
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
    if (!confirm("Are you sure you want to approve this submission? It will go live immediately on the event feed.")) return;
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

  const handleReject = (id: string) => {
    const reason = prompt("Enter optional rejection note/reason:");
    if (reason === null) return; // cancelled prompt
    setActionError(null);
    startTransition(async () => {
      const res = await rejectSubmission(id, reason);
      if (res.success) {
        router.refresh();
      } else {
        setActionError(res.error || "Failed to reject submission.");
      }
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
    if (!confirm("Are you sure you want to delete this event? This action is permanent and cannot be undone.")) return;
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

  // Filter events based on search query
  const filteredEvents = initialEvents.filter(
    (e) =>
      e.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      e.host.toLowerCase().includes(searchQuery.toLowerCase()) ||
      e.location.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-surface flex flex-col font-sans text-ink">
      {/* Top Header Deck */}
      <header className="sticky top-0 bg-canvas border-b border-ink/10 h-14 px-4 sm:px-6 flex items-center justify-between z-40 select-none">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-lg font-semibold tracking-tight text-ink">
            Highlander Hub
          </h1>
          <span className="bg-ink/5 border border-ink/10 text-muted font-mono text-[9px] px-1.5 py-0.5 rounded tracking-widest uppercase">
            MODERATOR
          </span>
        </div>

        <button
          onClick={handleLogout}
          disabled={isPending}
          className="flex items-center gap-1.5 text-xs text-muted hover:text-ink transition-colors font-sans py-2 px-3 hover:bg-surface border border-transparent hover:border-ink/5 rounded-md outline-none interactive-focus"
        >
          <IoLogOut size={15} />
          <span>Exit Deck</span>
        </button>
      </header>

      {/* Main Admin Content Area */}
      <main className="flex-1 w-full max-w-6xl mx-auto p-4 sm:p-6 space-y-6">
        {actionError && (
          <div className="p-4 bg-coral/10 border border-deep-coral/20 text-deep-coral rounded-md text-sm font-sans flex items-start gap-2 animate-field-reveal">
            <span>⚠️</span>
            <p className="flex-1 font-sans">{actionError}</p>
            <button onClick={() => setActionError(null)} className="text-deep-coral hover:text-ink transition-colors outline-none font-bold">
              ×
            </button>
          </div>
        )}

        {/* Custom Tab Switcher */}
        <div className="flex border-b border-ink/10 select-none items-center justify-between">
          <nav className="flex gap-6" role="tablist">
            <button
              role="tab"
              onClick={() => setActiveTab("submissions")}
              aria-selected={activeTab === "submissions"}
              className="tab"
            >
              Pending Submissions
              {initialSubmissions.length > 0 && (
                <span className="ml-2 font-mono text-[10px] bg-coral/10 text-deep-coral px-1.5 py-0.5 rounded-full font-semibold border border-deep-coral/10">
                  {initialSubmissions.length}
                </span>
              )}
            </button>
            <button
              role="tab"
              onClick={() => setActiveTab("events")}
              aria-selected={activeTab === "events"}
              className="tab"
            >
              Live Event Bulletin
              <span className="ml-2 font-mono text-[10px] bg-ink/5 text-muted px-1.5 py-0.5 rounded-full border border-ink/10">
                {initialEvents.length}
              </span>
            </button>
          </nav>

          {activeTab === "events" && (
            <div className="mb-2">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search live events..."
                className="bg-canvas border border-ink/15 rounded-md px-3 py-1.5 text-xs placeholder:text-muted/40 transition-colors focus:border-ink outline-none interactive-focus w-48 sm:w-64"
              />
            </div>
          )}
        </div>

        {/* Tab content 1: Submissions */}
        {activeTab === "submissions" && (
          <div className="space-y-6 animate-fade-up">
            {initialSubmissions.length === 0 ? (
              <div className="border border-ink/10 border-dashed rounded-xl p-12 text-center bg-canvas select-none">
                <span className="text-2xl">🌱</span>
                <h3 className="font-display text-base font-semibold mt-2 text-ink">
                  Inboxes Cleared!
                </h3>
                <p className="text-xs text-muted mt-1 max-w-[280px] mx-auto font-sans">
                  There are no pending submissions awaiting review right now. All manual uploads have been handled.
                </p>
              </div>
            ) : (
              <div className="grid gap-6 md:grid-cols-2">
                {initialSubmissions.map((sub) => (
                  <div
                    key={sub.id}
                    className="bg-canvas border border-ink/10 rounded-xl p-5 shadow-card hover:border-ink/20 transition-all flex flex-col justify-between"
                  >
                    <div>
                      {/* Submitter Box */}
                      <div className="flex items-center justify-between border-b border-ink/5 pb-3 mb-4 select-none">
                        <div className="text-[11px] font-mono tracking-wide text-muted leading-tight">
                          <span>SUBMITTED BY: </span>
                          <strong className="text-ink font-semibold">{sub.submitter_name}</strong>
                          {sub.submitter_org && ` (${sub.submitter_org})`}
                        </div>
                        <span className="font-mono text-[9px] text-muted">
                          {formatDate(sub.created_at)}
                        </span>
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

                        <p className="text-xs text-muted font-sans leading-relaxed whitespace-pre-line line-clamp-4 hover:line-clamp-none transition-all cursor-pointer">
                          {sub.description}
                        </p>

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

                    {/* Approve / Reject buttons */}
                    <div className="flex items-center gap-3 border-t border-ink/10 pt-4 mt-4 select-none">
                      <button
                        onClick={() => handleApprove(sub.id)}
                        disabled={isPending}
                        className="flex-1 min-h-10 bg-ink hover:bg-ink/90 active:scale-[0.99] text-canvas text-xs font-semibold rounded-md flex items-center justify-center gap-1.5 transition-all outline-none interactive-focus"
                      >
                        <IoCheckmark size={15} />
                        <span>Approve Submission</span>
                      </button>
                      <button
                        onClick={() => handleReject(sub.id)}
                        disabled={isPending}
                        className="min-h-10 px-4 border border-coral/30 hover:bg-coral/5 text-deep-coral text-xs font-semibold rounded-md flex items-center justify-center gap-1.5 transition-all outline-none interactive-focus"
                      >
                        <IoClose size={15} />
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
          <div className="space-y-4 animate-fade-up">
            {/* Event list rows */}
            {filteredEvents.length === 0 ? (
              <div className="border border-ink/10 border-dashed rounded-xl p-12 text-center bg-canvas select-none">
                <span className="text-2xl">🔍</span>
                <h3 className="font-display text-base font-semibold mt-2 text-ink">
                  No matches found
                </h3>
                <p className="text-xs text-muted mt-1 font-sans">
                  We couldn&apos;t find any live events matching your search terms.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredEvents.map((evt) => (
                  <div
                    key={evt.id}
                    className="bg-canvas border border-ink/10 rounded-xl p-4 shadow-card hover:border-ink/25 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
                  >
                    {/* Event Description Column */}
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      {/* Tonal category block */}
                      <div
                        className={`h-2.5 w-2.5 rounded-full mt-1.5 flex-shrink-0 ${
                          evt.category === "club"
                            ? "bg-highlander"
                            : evt.category === "academic" || evt.category === "community"
                            ? "bg-leaf"
                            : evt.category === "social" || evt.category === "arts"
                            ? "bg-coral"
                            : evt.category === "free_food"
                            ? "bg-gold"
                            : "bg-ink"
                        }`}
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 mb-1 select-none">
                          <span className="bg-ink/5 border border-ink/10 text-muted font-mono text-[9px] px-1 py-0.2 rounded font-semibold uppercase">
                            {evt.source}
                          </span>
                          <span className="font-mono text-[10px] text-muted">
                            {formatDate(evt.starts_at)}
                          </span>
                          {evt.is_locked && (
                            <span className="bg-gold/10 border border-gold/20 text-deep-gold font-mono text-[9px] px-1 py-0.2 rounded font-semibold tracking-wider">
                              LOCKED (MANUAL EDIT)
                            </span>
                          )}
                        </div>
                        <h4 className="font-display text-sm font-semibold text-ink leading-tight truncate">
                          {evt.title}
                        </h4>
                        <p className="text-xs text-muted font-sans mt-0.5 truncate max-w-2xl">
                          {evt.location} · Host: {evt.host} · {evt.description}
                        </p>
                      </div>
                    </div>

                    {/* Inline edit forms trigger and options */}
                    <div className="flex items-center gap-2 select-none self-end md:self-auto">
                      <button
                        onClick={() => startEditing(evt)}
                        disabled={isPending}
                        className="p-2 border border-ink/10 hover:bg-ink/5 text-muted hover:text-ink rounded-md transition-all outline-none interactive-focus"
                        title="Edit event details (automatically locks event)"
                      >
                        <IoPencil size={15} />
                      </button>
                      <button
                        onClick={() => handleDelete(evt.id)}
                        disabled={isPending}
                        className="p-2 border border-coral/20 hover:bg-coral/5 text-muted hover:text-deep-coral rounded-md transition-all outline-none interactive-focus"
                        title="Delete event from live site"
                      >
                        <IoTrash size={15} />
                      </button>
                    </div>
                  </div>
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
                      Edit Live Event
                    </h3>
                    <p className="text-[11px] font-sans text-muted mt-1 leading-normal">
                      Saving updates will automatically lock this event (`is_locked = true`) to protect it from automated overrides.
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
                  Save Corrections
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
    </div>
  );
}
