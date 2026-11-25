"use client";

import React, { useEffect, useId, useRef, useState } from "react";
import { IoCloseOutline, IoOpenOutline } from "react-icons/io5";
import { EVENT_CATEGORIES, EVENT_CATEGORY_LABELS } from "@/types/event";
import { FlyerPoster } from "@/components/events/FlyerPoster";
import { isPublicContentKind } from "@/lib/events/content-kind";
import { normalizeHttpUrl } from "@/lib/events/validation";
import type { AdminEventRow, AdminEventUpdatePayload } from "./types";
import { useAdminEventEdit } from "./useAdminEventEdit";

const INPUT =
  "w-full bg-canvas text-ink border border-ink/15 rounded-md py-2 px-3 text-base focus:border-ink outline-none interactive-focus transition-colors";

const DISCARD_MESSAGE = "Discard your unsaved changes to this listing?";

/**
 * Edits one live listing in a modal side panel. A native modal <dialog> keeps
 * focus inside, makes the page behind it inert, and closes on Escape; closing
 * returns focus to whatever opened it. Render with key={event.id}.
 */
export function AdminEventEditDrawer({
  event,
  isPending,
  error,
  onClose,
  onSave,
  onInvalid,
}: {
  event: AdminEventRow;
  isPending: boolean;
  /** The last save's failure, shown above the save button. */
  error: string | null;
  onClose: () => void;
  onSave: (payload: AdminEventUpdatePayload) => void;
  onInvalid: (message: string) => void;
}) {
  const { form, isDirty, setField, buildUpdatePayload } = useAdminEventEdit(event);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const titleId = useId();
  const [flyerBroken, setFlyerBroken] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const opener = document.activeElement as HTMLElement | null;
    const root = document.documentElement;
    const overflow = root.style.overflow;
    root.style.overflow = "hidden";
    dialog.showModal();
    return () => {
      root.style.overflow = overflow;
      dialog.close();
      opener?.focus?.();
    };
  }, []);

  const requestClose = () => {
    if (isPending) return;
    if (isDirty && !window.confirm(DISCARD_MESSAGE)) return;
    onClose();
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const built = buildUpdatePayload();
    if (built.ok) onSave(built.payload);
    else onInvalid(built.error);
  };

  const flyerUrl = normalizeHttpUrl(form.imageUrl);
  const sourceUrl = normalizeHttpUrl(event.source_url);
  const showFlyer = flyerUrl !== null && flyerBroken !== flyerUrl;

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      // Escape: ask before discarding edits instead of closing outright.
      onCancel={(e) => {
        e.preventDefault();
        requestClose();
      }}
      // The browser can still force a close (a repeated Escape); keep the
      // dashboard in step. While mounted, an open dialog means it was not.
      onClose={() => {
        if (!dialogRef.current?.open) onClose();
      }}
      // A click on the backdrop targets the dialog itself.
      onClick={(e) => {
        if (e.target === dialogRef.current) requestClose();
      }}
      className="fixed inset-0 m-0 ml-auto h-full max-h-none w-full max-w-[540px] bg-canvas p-0 text-ink sm:rounded-l-xl border-l border-ink/10 shadow-card backdrop:bg-scrim/35 backdrop:backdrop-blur-sm animate-scale-in"
    >
      <form
        ref={formRef}
        onSubmit={submit}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            formRef.current?.requestSubmit();
          }
        }}
        className="flex h-full flex-col"
      >
        <header className="flex items-start justify-between gap-4 border-b border-ink/10 px-6 pt-6 pb-4 sm:px-8">
          <div className="min-w-0">
            <h2 id={titleId} className="font-display text-lg font-semibold text-ink leading-tight">
              Edit event
            </h2>
            <p className="text-[0.6875rem] font-sans text-muted mt-1 leading-normal">
              Saving locks this listing so automated imports won&apos;t overwrite your
              changes.
            </p>
          </div>
          <button
            type="button"
            onClick={requestClose}
            aria-label="Close"
            className="-mr-2 p-2 text-muted hover:text-ink rounded-md outline-none interactive-focus press"
          >
            <IoCloseOutline size={20} aria-hidden />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-6 sm:px-8 space-y-4">
          <div className="flex gap-4 rounded-lg border border-ink/10 bg-surface p-3">
            {showFlyer ? (
              <div className="flex h-[var(--flyer-max-h)] w-[var(--flyer-max-w)] shrink-0 items-center justify-center [--flyer-max-h:120px] [--flyer-max-w:96px]">
                <FlyerPoster
                  key={flyerUrl}
                  src={flyerUrl}
                  alt={`${form.title} flyer`}
                  width={96}
                  className="rounded bg-ink/[0.05] ring-1 ring-ink/10"
                  onError={() => setFlyerBroken(flyerUrl)}
                />
              </div>
            ) : (
              <div className="flex h-[120px] w-[96px] shrink-0 items-center justify-center rounded border border-dashed border-ink/15 bg-canvas px-2 text-center text-[0.625rem] leading-tight text-muted">
                {flyerUrl ? "Flyer didn't load" : "No flyer"}
              </div>
            )}
            <div className="min-w-0 space-y-1.5 text-xs font-sans text-muted">
              <p>Check details against the flyer and the original post.</p>
              <div className="flex flex-col items-start gap-1">
                {sourceUrl && (
                  <ExternalLink href={sourceUrl}>Source post</ExternalLink>
                )}
                {isPublicContentKind(event.content_kind) && (
                  <ExternalLink href={`/events/${encodeURIComponent(event.id)}`}>
                    View on site
                  </ExternalLink>
                )}
              </div>
              {event.is_locked && (
                <p className="text-deep-gold">Already locked by an earlier edit.</p>
              )}
            </div>
          </div>

          <Field label="Title">
            {(id) => (
              <input
                id={id}
                type="text"
                value={form.title}
                onChange={(e) => setField("title", e.target.value)}
                required
                className={INPUT}
              />
            )}
          </Field>

          <Field label="Description">
            {(id) => (
              <textarea
                id={id}
                value={form.description}
                onChange={(e) => setField("description", e.target.value)}
                rows={4}
                className={`${INPUT} resize-y font-sans leading-relaxed`}
              />
            )}
          </Field>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Starts">
              {(id) => (
                <input
                  id={id}
                  type="datetime-local"
                  value={form.startsAt}
                  onChange={(e) => setField("startsAt", e.target.value)}
                  required
                  className={INPUT}
                />
              )}
            </Field>
            <Field label="Ends" optional>
              {(id) => (
                <input
                  id={id}
                  type="datetime-local"
                  value={form.endsAt}
                  onChange={(e) => setField("endsAt", e.target.value)}
                  className={INPUT}
                />
              )}
            </Field>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Location">
              {(id) => (
                <input
                  id={id}
                  type="text"
                  value={form.location}
                  onChange={(e) => setField("location", e.target.value)}
                  required
                  className={INPUT}
                />
              )}
            </Field>
            <Field label="Host">
              {(id) => (
                <input
                  id={id}
                  type="text"
                  value={form.host}
                  onChange={(e) => setField("host", e.target.value)}
                  required
                  className={INPUT}
                />
              )}
            </Field>
          </div>

          <Field
            label="Listing type"
            hint="Only Event and Deadline appear on the public feed. Use Application / Fundraiser / Other to correct a misclassified import."
          >
            {(id, hintId) => (
              <select
                id={id}
                aria-describedby={hintId}
                value={form.contentKind}
                onChange={(e) => setField("contentKind", e.target.value)}
                className={INPUT}
              >
                <option value="student_event">Event</option>
                <option value="student_deadline">Deadline</option>
                <option value="student_application">
                  Application (hidden from public)
                </option>
                <option value="fundraiser">Fundraiser (hidden from public)</option>
                <option value="other">Other (hidden from public)</option>
              </select>
            )}
          </Field>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Category">
              {(id) => (
                <select
                  id={id}
                  value={form.category}
                  onChange={(e) => setField("category", e.target.value)}
                  className={INPUT}
                >
                  {EVENT_CATEGORIES.map((value) => (
                    <option key={value} value={value}>
                      {EVENT_CATEGORY_LABELS[value]}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label="Instagram handle" optional>
              {(id) => (
                <input
                  id={id}
                  type="text"
                  value={form.hostHandle}
                  onChange={(e) => setField("hostHandle", e.target.value)}
                  placeholder="acm.ucr"
                  autoCapitalize="none"
                  spellCheck={false}
                  className={INPUT}
                />
              )}
            </Field>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Flyer image URL" optional>
              {(id) => (
                <input
                  id={id}
                  type="url"
                  value={form.imageUrl}
                  onChange={(e) => setField("imageUrl", e.target.value)}
                  spellCheck={false}
                  className={INPUT}
                />
              )}
            </Field>
            <Field label="RSVP link" optional>
              {(id) => (
                <input
                  id={id}
                  type="url"
                  value={form.rsvpUrl}
                  onChange={(e) => setField("rsvpUrl", e.target.value)}
                  spellCheck={false}
                  className={INPUT}
                />
              )}
            </Field>
          </div>

          <fieldset className="grid grid-cols-2 gap-4 border-t border-ink/5 pt-4">
            <legend className="sr-only">Listing details</legend>
            <label className="flex items-center gap-2 cursor-pointer font-sans text-sm text-ink">
              <input
                type="checkbox"
                checked={form.rsvpRequired}
                onChange={(e) => setField("rsvpRequired", e.target.checked)}
                className="h-4 w-4 accent-ink rounded text-ink outline-none interactive-focus"
              />
              <span>RSVP required</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer font-sans text-sm text-ink">
              <input
                type="checkbox"
                checked={form.hasFreeFood}
                onChange={(e) => setField("hasFreeFood", e.target.checked)}
                className="h-4 w-4 accent-ink rounded text-ink outline-none interactive-focus"
              />
              <span>Free food</span>
            </label>
          </fieldset>
        </div>

        <footer className="border-t border-ink/10 px-6 py-4 sm:px-8 space-y-3">
          {error && (
            <p role="alert" className="text-xs text-deep-coral font-sans">
              {error}
            </p>
          )}
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={isPending}
              className="flex-1 min-h-11 bg-ink hover:bg-ink/90 text-canvas text-xs font-semibold rounded-md outline-none interactive-focus press disabled:opacity-60"
            >
              {isPending ? "Saving…" : "Save changes"}
            </button>
            <button
              type="button"
              onClick={requestClose}
              disabled={isPending}
              className="px-6 min-h-11 border border-ink/10 hover:bg-ink/5 text-muted hover:text-ink text-xs font-semibold rounded-md outline-none interactive-focus press disabled:opacity-60"
            >
              Cancel
            </button>
          </div>
          <p className="hidden sm:block text-[0.6875rem] text-muted font-sans">
            <kbd className="font-sans">⌘</kbd> + <kbd className="font-sans">Enter</kbd> saves
            · <kbd className="font-sans">Esc</kbd> closes
          </p>
        </footer>
      </form>
    </dialog>
  );
}

function Field({
  label,
  optional = false,
  hint,
  children,
}: {
  label: string;
  optional?: boolean;
  hint?: string;
  children: (id: string, hintId: string | undefined) => React.ReactNode;
}) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-[0.75rem] font-sans text-muted">
        {label}
        {optional && <span className="text-faint"> (optional)</span>}
      </label>
      {children(id, hintId)}
      {hint && (
        <p id={hintId} className="text-[0.6875rem] font-sans text-muted leading-normal">
          {hint}
        </p>
      )}
    </div>
  );
}

function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-ink underline decoration-ink/20 underline-offset-2 outline-none interactive-focus rounded-sm active:opacity-70"
    >
      {children}
      <IoOpenOutline size={12} aria-hidden />
    </a>
  );
}
