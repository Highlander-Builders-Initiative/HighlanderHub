"use client";

import React from "react";
import { IoClose } from "react-icons/io5";
import type {
  AdminEventEditForm,
  SetAdminEventEditField,
} from "./useAdminEventEdit";

export function AdminEventEditDrawer({
  form,
  setField,
  onClose,
  onSubmit,
  isPending,
}: {
  form: AdminEventEditForm;
  setField: SetAdminEventEditField;
  onClose: () => void;
  onSubmit: (e: React.FormEvent) => void;
  isPending: boolean;
}) {
  return (
    <div className="fixed inset-0 bg-ink/35 backdrop-blur-sm z-50 flex items-center justify-end animate-fade-in p-4 sm:p-0">
      <div className="bg-canvas w-full max-w-[540px] h-full sm:h-screen sm:rounded-l-xl border-l border-ink/10 p-6 sm:p-8 flex flex-col justify-between overflow-y-auto animate-scale-in">
        <form onSubmit={onSubmit} className="space-y-6 flex-1 flex flex-col justify-between">
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
                onClick={onClose}
                className="p-2 text-muted hover:text-ink transition-colors rounded-md outline-none interactive-focus"
              >
                <IoClose size={20} />
              </button>
            </header>

            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className="block text-[12px] font-sans text-muted">Event Title</label>
                <input
                  type="text"
                  value={form.title}
                  onChange={(e) => setField("title", e.target.value)}
                  required
                  className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors"
                />
              </div>

              <div className="space-y-1.5">
                <label className="block text-[12px] font-sans text-muted">Description</label>
                <textarea
                  value={form.description}
                  onChange={(e) => setField("description", e.target.value)}
                  rows={4}
                  className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors resize-y font-sans leading-relaxed"
                />
              </div>

              <div className="grid grid-cols-2 gap-4 select-none">
                <div className="space-y-1.5">
                  <label className="block text-[12px] font-sans text-muted">Starts At</label>
                  <input
                    type="datetime-local"
                    value={form.startsAt}
                    onChange={(e) => setField("startsAt", e.target.value)}
                    required
                    className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="block text-[12px] font-sans text-muted">Ends At (Optional)</label>
                  <input
                    type="datetime-local"
                    value={form.endsAt}
                    onChange={(e) => setField("endsAt", e.target.value)}
                    className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="block text-[12px] font-sans text-muted">Location</label>
                  <input
                    type="text"
                    value={form.location}
                    onChange={(e) => setField("location", e.target.value)}
                    required
                    className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="block text-[12px] font-sans text-muted">Host Organizer</label>
                  <input
                    type="text"
                    value={form.host}
                    onChange={(e) => setField("host", e.target.value)}
                    required
                    className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="block text-[12px] font-sans text-muted">Category</label>
                  <select
                    value={form.category}
                    onChange={(e) => setField("category", e.target.value)}
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
                    value={form.hostHandle}
                    onChange={(e) => setField("hostHandle", e.target.value)}
                    placeholder="acm.ucr"
                    className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="block text-[12px] font-sans text-muted">Flyer Image URL (Optional)</label>
                  <input
                    type="text"
                    value={form.imageUrl}
                    onChange={(e) => setField("imageUrl", e.target.value)}
                    className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="block text-[12px] font-sans text-muted">RSVP Link (Optional)</label>
                  <input
                    type="text"
                    value={form.rsvpUrl}
                    onChange={(e) => setField("rsvpUrl", e.target.value)}
                    className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-sm focus:border-ink outline-none interactive-focus transition-colors font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 border-t border-ink/5 pt-4 select-none">
                <label className="flex items-center gap-2 cursor-pointer font-sans text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={form.isFree}
                    onChange={(e) => setField("isFree", e.target.checked)}
                    className="h-4 w-4 accent-ink rounded text-ink outline-none interactive-focus"
                  />
                  <span>This event is FREE</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer font-sans text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={form.rsvpRequired}
                    onChange={(e) => setField("rsvpRequired", e.target.checked)}
                    className="h-4 w-4 accent-ink rounded text-ink outline-none interactive-focus"
                  />
                  <span>RSVP Required</span>
                </label>
              </div>
            </div>
          </div>

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
              onClick={onClose}
              className="px-6 min-h-11 border border-ink/10 hover:bg-ink/5 text-muted hover:text-ink text-xs font-semibold rounded-md transition-colors outline-none interactive-focus"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
