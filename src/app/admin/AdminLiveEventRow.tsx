"use client";

import React, { useMemo, useState } from "react";
import { IoPencil, IoTrash } from "react-icons/io5";
import { EventListRowTimeColumn } from "@/components/events/EventListRowTimeColumn";
import { FlyerPoster } from "@/components/events/FlyerPoster";
import { eventRowToCampusEvent } from "@/lib/events/map-event-row";
import type { AdminEventRow } from "./types";

export function AdminLiveEventRow({
  event,
  feedIndex,
  formatDate,
  onEdit,
  onDelete,
  isActionPending,
}: {
  event: AdminEventRow;
  feedIndex: number;
  formatDate: (iso: string) => string;
  onEdit: () => void;
  onDelete: () => void;
  isActionPending: boolean;
}) {
  const [imageBroken, setImageBroken] = useState(false);
  const campusEvent = useMemo(() => eventRowToCampusEvent(event), [event]);
  const showImage = Boolean(campusEvent.imageUrl) && !imageBroken;

  return (
    <article className="bg-canvas border border-ink/10 rounded-xl shadow-card hover:border-ink/25 transition-all overflow-hidden flex flex-col sm:flex-row sm:items-stretch">
      <div className="flex flex-1 min-w-0 min-h-[6rem]">
        <EventListRowTimeColumn
          startsAt={campusEvent.startsAt}
          category={campusEvent.category}
          prefix={
            <span className="font-mono text-[10px] text-muted tabular-nums mb-1">
              #{feedIndex + 1}
            </span>
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
              sizes="80px"
              className="rounded bg-ink/[0.05] shadow-[0_1px_2px_rgba(15,17,21,0.06),0_3px_8px_-2px_rgba(15,17,21,0.08)] ring-1 ring-ink/10"
              onError={() => setImageBroken(true)}
            />
          </div>
        ) : (
          <div className="my-2 ml-3 h-[100px] w-[80px] shrink-0 self-center">
            <div
              className="flex h-full w-full items-center justify-center rounded border border-dashed border-ink/15 bg-surface text-[9px] font-sans text-muted text-center px-1 leading-tight"
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
            <span className="font-mono text-[10px] text-muted">
              {formatDate(event.starts_at)}
            </span>
            {event.is_locked && (
              <span className="bg-gold/10 border border-gold/20 text-deep-gold font-mono text-[9px] px-1 py-0.5 rounded font-semibold tracking-wider">
                Locked
              </span>
            )}
          </div>
          <h4 className="font-display text-sm font-semibold text-ink leading-snug">
            {campusEvent.title}
          </h4>
          <p className="text-xs text-muted font-sans mt-1 line-clamp-2">
            {campusEvent.location} · {campusEvent.host}
          </p>
          {campusEvent.description && (
            <p className="text-xs text-muted/80 font-sans mt-1 line-clamp-1">
              {campusEvent.description}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 border-t sm:border-t-0 sm:border-l border-ink/10 p-3 sm:p-4 sm:flex-col sm:justify-center shrink-0">
        <button
          type="button"
          onClick={onEdit}
          disabled={isActionPending}
          className="flex-1 sm:flex-none min-h-9 px-3 border border-ink/10 hover:bg-ink/5 text-muted hover:text-ink rounded-md transition-all outline-none interactive-focus flex items-center justify-center gap-1.5 text-xs font-semibold disabled:opacity-50"
        >
          <IoPencil size={14} aria-hidden />
          <span>Edit</span>
        </button>
        <button
          type="button"
          onClick={onDelete}
          disabled={isActionPending}
          className="flex-1 sm:flex-none min-h-9 px-3 border border-coral/20 hover:bg-coral/5 text-muted hover:text-deep-coral rounded-md transition-all outline-none interactive-focus flex items-center justify-center gap-1.5 text-xs font-semibold disabled:opacity-50"
        >
          <IoTrash size={14} aria-hidden />
          <span>Delete</span>
        </button>
      </div>
    </article>
  );
}
