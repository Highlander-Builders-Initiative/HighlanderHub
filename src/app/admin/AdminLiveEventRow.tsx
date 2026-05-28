"use client";

import React, { useState } from "react";
import { IoPencil, IoTrash } from "react-icons/io5";
import { formatTimeParts } from "@/lib/dates";
import { CATEGORY_RAIL } from "@/lib/category-colors";
import type { CampusEvent } from "@/types/event";
import type { AdminEventRow } from "./types";

export function AdminLiveEventRow({
  event,
  feedIndex,
  formatDate,
  onEdit,
  onDelete,
  disabled,
}: {
  event: AdminEventRow;
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
