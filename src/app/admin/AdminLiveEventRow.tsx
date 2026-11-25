"use client";

import React, { useMemo, useState } from "react";
import { IoOpenOutline, IoPencilOutline, IoTrashOutline } from "react-icons/io5";
import { EventListRowTimeColumn } from "@/components/events/EventListRowTimeColumn";
import { FlyerPoster } from "@/components/events/FlyerPoster";
import { eventRowToCampusEvent } from "@/lib/events/map-event-row";
import {
  EVENT_CONTENT_KIND_LABELS,
  isPublicContentKind,
} from "@/lib/events/content-kind";
import { eventTimeLabel, formatDayShort } from "@/lib/dates";
import type { AdminEventRow } from "./types";

export const ADMIN_TAG =
  "border text-[0.5625rem] px-1 py-0.5 rounded font-semibold";

export function AdminLiveEventRow({
  event,
  feedIndex,
  onEdit,
  onDelete,
  isActionPending,
  error,
}: {
  event: AdminEventRow;
  /** Position on the public feed; null for listings the feed never shows. */
  feedIndex: number | null;
  onEdit: () => void;
  onDelete: () => void;
  isActionPending: boolean;
  /** The last delete's failure for this listing. */
  error: string | null;
}) {
  const [imageBroken, setImageBroken] = useState(false);
  const campusEvent = useMemo(() => eventRowToCampusEvent(event), [event]);
  const showImage = Boolean(campusEvent.imageUrl) && !imageBroken;
  const isPublic = isPublicContentKind(event.content_kind);
  // The whole span, so a listing missing its end time shows at a glance.
  const when = `${formatDayShort(campusEvent.startsAt)} · ${eventTimeLabel(campusEvent, "span")}`;

  return (
    <article
      aria-label={campusEvent.title}
      className="bg-canvas border border-ink/10 rounded-xl shadow-card hover:border-ink/25 transition-colors overflow-clip flex flex-col sm:flex-row sm:items-stretch"
    >
      <div className="flex flex-1 min-w-0 min-h-[6rem]">
        <EventListRowTimeColumn
          startsAt={campusEvent.startsAt}
          category={campusEvent.category}
          prefix={
            feedIndex !== null ? (
              <span className="text-[0.625rem] text-muted tabular-nums mb-1">
                #{feedIndex + 1}
              </span>
            ) : undefined
          }
        />

        {showImage ? (
          // Same whole-flyer 4:5 slot as the public EventCard, so review shows
          // exactly what students see. EventFlyerImage keeps arbitrary hosts
          // off the next/image optimizer; CSP img-src still governs which hosts
          // load, so blocked/broken flyers fall back via onError.
          <div className="my-2 ml-3 flex h-[var(--flyer-max-h)] w-[var(--flyer-max-w)] shrink-0 items-center justify-center self-center [--flyer-max-h:100px] [--flyer-max-w:80px]">
            <FlyerPoster
              src={campusEvent.imageUrl!}
              alt={`${campusEvent.title} flyer`}
              width={80}
              className="rounded bg-ink/[0.05] shadow-flyer ring-1 ring-ink/10"
              onError={() => setImageBroken(true)}
            />
          </div>
        ) : (
          <div className="my-2 ml-3 h-[100px] w-[80px] shrink-0 self-center">
            <div
              className="flex h-full w-full items-center justify-center rounded border border-dashed border-ink/15 bg-surface text-[0.5625rem] font-sans text-muted text-center px-1 leading-tight"
              aria-label="No flyer image"
            >
              No flyer
            </div>
          </div>
        )}

        <div className="min-w-0 flex-1 py-3 pr-3 pl-3 sm:pl-4">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mb-1">
            <span className={`${ADMIN_TAG} bg-ink/5 border-ink/10 text-muted uppercase tracking-[0.08em]`}>
              {event.source}
            </span>
            <span className="text-[0.625rem] text-muted tabular-nums">{when}</span>
            {!isPublic && (
              <span className={`${ADMIN_TAG} bg-coral/10 border-coral/20 text-deep-coral`}>
                Hidden · {EVENT_CONTENT_KIND_LABELS[event.content_kind]}
              </span>
            )}
            {event.is_locked && (
              <span className={`${ADMIN_TAG} bg-gold/10 border-gold/20 text-deep-gold`}>
                Locked
              </span>
            )}
          </div>
          <h3 className="font-display text-sm font-semibold text-ink leading-snug">
            {campusEvent.title}
          </h3>
          <p className="text-xs text-muted font-sans mt-1 line-clamp-2">
            {campusEvent.location} · {campusEvent.host}
          </p>
          {campusEvent.description && (
            <p className="text-xs text-muted/80 font-sans mt-1 line-clamp-1">
              {campusEvent.description}
            </p>
          )}
          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
            {campusEvent.sourceUrl && (
              <RowLink href={campusEvent.sourceUrl}>Source post</RowLink>
            )}
            {isPublic && (
              <RowLink href={`/events/${encodeURIComponent(event.id)}`}>View on site</RowLink>
            )}
          </div>
          {error && (
            <p role="alert" className="mt-2 text-xs text-deep-coral font-sans">
              {error}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 border-t sm:border-t-0 sm:border-l border-ink/10 p-3 sm:p-4 sm:flex-col sm:justify-center shrink-0">
        <button
          type="button"
          onClick={onEdit}
          disabled={isActionPending}
          aria-label={`Edit ${campusEvent.title}`}
          className="flex-1 sm:flex-none min-h-9 px-3 border border-ink/10 hover:bg-ink/5 text-muted hover:text-ink rounded-md outline-none interactive-focus press flex items-center justify-center gap-1.5 text-xs font-semibold disabled:opacity-50"
        >
          <IoPencilOutline size={14} aria-hidden />
          <span aria-hidden>Edit</span>
        </button>
        <button
          type="button"
          onClick={onDelete}
          disabled={isActionPending}
          aria-label={`Delete ${campusEvent.title}`}
          className="flex-1 sm:flex-none min-h-9 px-3 border border-coral/20 hover:bg-coral/5 text-muted hover:text-deep-coral rounded-md outline-none interactive-focus press flex items-center justify-center gap-1.5 text-xs font-semibold disabled:opacity-50"
        >
          <IoTrashOutline size={14} aria-hidden />
          <span aria-hidden>Delete</span>
        </button>
      </div>
    </article>
  );
}

export function RowLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink underline decoration-ink/20 underline-offset-2 outline-none interactive-focus rounded-sm active:opacity-70"
    >
      {children}
      <IoOpenOutline size={12} aria-hidden />
    </a>
  );
}
