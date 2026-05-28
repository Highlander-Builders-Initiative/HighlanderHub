"use client";

import React from "react";
import {
  IoCheckmark,
  IoClose,
  IoCalendar,
  IoLocation,
  IoPerson,
  IoLink,
  IoMailOutline,
  IoChevronDown,
  IoChevronUp,
} from "react-icons/io5";
import type { SubmissionRow } from "./types";

export function AdminSubmissionCard({
  submission,
  formatDate,
  isExpanded,
  onToggleDescription,
  onApprove,
  onReject,
  disabled,
}: {
  submission: SubmissionRow;
  formatDate: (iso: string) => string;
  isExpanded: boolean;
  onToggleDescription: () => void;
  onApprove: () => void;
  onReject: () => void;
  disabled: boolean;
}) {
  const sub = submission;

  return (
    <div className="bg-canvas border border-ink/10 rounded-xl p-5 shadow-card hover:border-ink/20 transition-all flex flex-col justify-between">
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

          {sub.image_url && (
            <div className="relative border border-ink/10 rounded-lg overflow-hidden max-h-[220px] bg-surface flex justify-center group select-none">
              <img
                src={sub.image_url}
                alt="Flyer image"
                className="object-contain max-h-[220px] hover:scale-[1.02] transition-transform duration-200"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = "none";
                }}
              />
            </div>
          )}

          <div>
            <p
              className={`text-xs text-muted font-sans leading-relaxed whitespace-pre-line ${
                isExpanded ? "" : "line-clamp-4"
              }`}
            >
              {sub.description}
            </p>
            {sub.description.length > 200 && (
              <button
                type="button"
                onClick={onToggleDescription}
                className="mt-1.5 inline-flex items-center gap-0.5 text-[11px] font-semibold text-ink hover:underline outline-none interactive-focus"
              >
                {isExpanded ? (
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
          onClick={onApprove}
          disabled={disabled}
          className="flex-1 min-h-10 bg-ink hover:bg-ink/90 active:scale-[0.99] text-canvas text-xs font-semibold rounded-md flex items-center justify-center gap-1.5 transition-all outline-none interactive-focus disabled:opacity-50"
        >
          <IoCheckmark size={15} aria-hidden />
          <span>Approve & publish</span>
        </button>
        <button
          type="button"
          onClick={onReject}
          disabled={disabled}
          className="min-h-10 px-4 border border-coral/30 hover:bg-coral/5 text-deep-coral text-xs font-semibold rounded-md flex items-center justify-center gap-1.5 transition-all outline-none interactive-focus disabled:opacity-50"
        >
          <IoClose size={15} aria-hidden />
          <span>Reject</span>
        </button>
      </div>
    </div>
  );
}
