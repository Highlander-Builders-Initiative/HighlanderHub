"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { IoCheckmark, IoOpenOutline } from "react-icons/io5";
import clsx from "clsx";
import { FlyerPoster } from "@/components/events/FlyerPoster";
import { formatDayShort, formatTimeRange } from "@/lib/dates";
import { eventRowToCampusEvent } from "@/lib/events/map-event-row";
import { duplicateMergeChanges } from "./duplicate-merge";
import type { AdminPendingAction } from "./pending-action";
import {
  type AdminEventRow,
  type DuplicateReviewPair,
  duplicatePairKey,
} from "./types";

const OUTLINE_BUTTON =
  "min-h-9 px-3 border border-ink/10 hover:bg-ink/5 text-muted hover:text-ink rounded-md transition-colors outline-none interactive-focus inline-flex items-center justify-center gap-1.5 text-xs font-semibold disabled:opacity-50";

function when(event: AdminEventRow): string {
  return `${formatDayShort(event.starts_at)} · ${formatTimeRange(
    event.starts_at,
    event.ends_at ?? undefined
  )}`;
}

function hostLabel(event: AdminEventRow): string {
  return event.host_handle ? `${event.host} (@${event.host_handle})` : event.host;
}

const normalized = (value: string) => value.trim().toLowerCase();

export function AdminDuplicateReview({
  pairs,
  queueError,
  feedPositionById,
  pendingAction,
  onMerge,
  onDistinct,
}: {
  pairs: DuplicateReviewPair[];
  queueError: string | null;
  feedPositionById: Map<string, number>;
  pendingAction: AdminPendingAction | null;
  onMerge: (pairKey: string, kept: AdminEventRow, removed: AdminEventRow) => void;
  onDistinct: (pairKey: string, pair: DuplicateReviewPair) => void;
}) {
  return (
    <section aria-labelledby="duplicate-review-heading" className="space-y-3">
      <div className="flex items-baseline justify-between gap-4 border-b border-ink/10 pb-3">
        <h2
          id="duplicate-review-heading"
          className="font-display text-base font-semibold text-ink"
        >
          Possible duplicates
        </h2>
        {pairs.length > 0 && (
          <p className="text-[11px] text-muted tabular-nums">
            {pairs.length} to review
          </p>
        )}
      </div>

      {queueError ? (
        <p role="alert" className="text-xs text-deep-coral font-sans">
          The review queue didn&apos;t load: {queueError}
        </p>
      ) : pairs.length === 0 ? (
        <p className="text-xs text-muted font-sans">
          Nothing to review. When two upcoming listings look alike but no rule
          merged them, the pipeline adds the pair here on its next run.
        </p>
      ) : (
        <>
          <p className="text-xs text-muted font-sans max-w-[70ch]">
            Keep one listing to merge a pair: the other comes off the site and its
            Instagram post points at the one you kept, so it won&apos;t come back.
            Pairs marked different both stay up and aren&apos;t flagged again.
          </p>
          <ol className="space-y-4">
            {pairs.map((pair) => {
              const key = duplicatePairKey(pair);
              return (
                <DuplicatePairCard
                  key={key}
                  pair={pair}
                  feedPositionById={feedPositionById}
                  pending={
                    (pendingAction?.type === "merge" ||
                      pendingAction?.type === "distinct") &&
                    pendingAction.id === key
                      ? pendingAction.type
                      : null
                  }
                  onMerge={(kept, removed) => onMerge(key, kept, removed)}
                  onDistinct={() => onDistinct(key, pair)}
                />
              );
            })}
          </ol>
        </>
      )}
    </section>
  );
}

function DuplicatePairCard({
  pair,
  feedPositionById,
  pending,
  onMerge,
  onDistinct,
}: {
  pair: DuplicateReviewPair;
  feedPositionById: Map<string, number>;
  pending: "merge" | "distinct" | null;
  onMerge: (kept: AdminEventRow, removed: AdminEventRow) => void;
  onDistinct: () => void;
}) {
  const [keptId, setKeptId] = useState<string | null>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const listings = [pair.first, pair.second];
  const kept = listings.find((event) => event.id === keptId) ?? null;
  const removed = kept ? listings.find((event) => event.id !== keptId)! : null;
  const additions = kept && removed ? duplicateMergeChanges(kept, removed).additions : [];

  useEffect(() => {
    if (keptId) confirmRef.current?.focus();
  }, [keptId]);

  const differs = {
    title: normalized(pair.first.title) !== normalized(pair.second.title),
    when: when(pair.first) !== when(pair.second),
    where: normalized(pair.first.location) !== normalized(pair.second.location),
    host: normalized(hostLabel(pair.first)) !== normalized(hostLabel(pair.second)),
  };

  return (
    <li className="bg-canvas border border-ink/10 rounded-xl shadow-card overflow-hidden">
      <div className="grid sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-ink/10">
        {listings.map((event, index) => (
          <DuplicateListing
            key={event.id}
            corner={index === 0 ? "rounded-t-xl sm:rounded-tr-none sm:rounded-tl-xl" : "sm:rounded-tr-xl"}
            event={event}
            feedIndex={feedPositionById.get(event.id)}
            differs={differs}
            outcome={keptId === null ? null : event.id === keptId ? "kept" : "removed"}
            disabled={pending !== null}
            onKeep={() => setKeptId(event.id)}
          />
        ))}
      </div>

      <div className="border-t border-ink/10 px-4 py-3">
        {kept && removed ? (
          <div
            role="group"
            aria-label="Confirm merge"
            className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0 space-y-0.5">
              <p className="text-sm text-ink font-sans">
                Keep <span className="font-semibold">{kept.title}</span> and remove
                the other listing.
              </p>
              <p className="text-xs text-muted font-sans">
                {additions.length > 0
                  ? `The kept listing also takes the other's ${formatList(additions)}.`
                  : "The kept listing already has every detail the other one adds."}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => setKeptId(null)}
                disabled={pending !== null}
                className={OUTLINE_BUTTON}
              >
                Cancel
              </button>
              <button
                ref={confirmRef}
                type="button"
                onClick={() => onMerge(kept, removed)}
                disabled={pending !== null}
                className="min-h-9 px-4 bg-ink text-canvas rounded-md transition-opacity hover:opacity-85 outline-none interactive-focus inline-flex items-center justify-center text-xs font-semibold disabled:opacity-50"
              >
                {pending === "merge" ? "Merging…" : "Merge listings"}
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted font-sans">
              Same event? Keep the better listing above.
            </p>
            <button
              type="button"
              onClick={onDistinct}
              disabled={pending !== null}
              className={OUTLINE_BUTTON}
            >
              {pending === "distinct" ? "Saving…" : "Different events"}
            </button>
          </div>
        )}
      </div>
    </li>
  );
}

function DuplicateListing({
  event,
  corner,
  feedIndex,
  differs,
  outcome,
  disabled,
  onKeep,
}: {
  event: AdminEventRow;
  /** The card corner this half sits in, so the kept outline follows it. */
  corner: string;
  feedIndex: number | undefined;
  differs: Record<"title" | "when" | "where" | "host", boolean>;
  outcome: "kept" | "removed" | null;
  disabled: boolean;
  onKeep: () => void;
}) {
  const [imageBroken, setImageBroken] = useState(false);
  const campusEvent = useMemo(() => eventRowToCampusEvent(event), [event]);
  const showImage = Boolean(campusEvent.imageUrl) && !imageBroken;
  // Values the two listings disagree on read in ink; shared ones recede.
  const tone = (field: keyof typeof differs) =>
    differs[field] ? "text-ink" : "text-muted";

  return (
    <article
      aria-label={event.title}
      className={clsx(
        "flex flex-col gap-3 p-4 transition-opacity duration-200",
        corner,
        outcome === "kept" && "ring-1 ring-inset ring-ink",
        outcome === "removed" && "opacity-55"
      )}
    >
      <div className="flex items-center gap-2 text-[10px] text-muted">
        {feedIndex !== undefined && (
          <span className="tabular-nums">#{feedIndex + 1}</span>
        )}
        <span className="bg-ink/5 border border-ink/10 px-1 py-0.5 rounded font-semibold uppercase text-[9px]">
          {event.source}
        </span>
        {event.is_locked && (
          <span className="bg-gold/10 border border-gold/20 text-deep-gold text-[9px] px-1 py-0.5 rounded font-semibold">
            Locked
          </span>
        )}
        {outcome === "removed" && <span className="ml-auto">Removed on merge</span>}
      </div>

      <div className="flex gap-3 min-w-0">
        {showImage ? (
          <div className="flex h-[var(--flyer-max-h)] w-[var(--flyer-max-w)] shrink-0 items-center justify-center [--flyer-max-h:80px] [--flyer-max-w:64px]">
            <FlyerPoster
              src={campusEvent.imageUrl!}
              alt={`${event.title} flyer`}
              width={64}
              className="rounded bg-ink/[0.05] ring-1 ring-ink/10"
              onError={() => setImageBroken(true)}
            />
          </div>
        ) : (
          <div
            className="flex h-[80px] w-[64px] shrink-0 items-center justify-center rounded border border-dashed border-ink/15 bg-surface text-[9px] text-muted text-center leading-tight"
            aria-label="No flyer image"
          >
            No flyer
          </div>
        )}

        <div className="min-w-0 flex-1 space-y-1.5">
          <h3
            className={clsx(
              "font-sans text-sm font-semibold leading-snug",
              tone("title")
            )}
          >
            {event.title}
          </h3>
          <dl className="grid grid-cols-[3rem_1fr] gap-x-2 gap-y-0.5 text-xs font-sans">
            <dt className="text-muted">When</dt>
            <dd className={clsx("tabular-nums", tone("when"))}>{when(event)}</dd>
            <dt className="text-muted">Where</dt>
            <dd className={clsx("break-words", tone("where"))}>{event.location}</dd>
            <dt className="text-muted">Host</dt>
            <dd className={clsx("break-words", tone("host"))}>{hostLabel(event)}</dd>
          </dl>
        </div>
      </div>

      {event.description && (
        <p className="text-xs text-muted font-sans line-clamp-3">
          {event.description}
        </p>
      )}

      <div className="mt-auto flex flex-wrap items-center gap-3 pt-1">
        {outcome === "kept" ? (
          <span className="min-h-9 inline-flex items-center gap-1.5 text-xs font-semibold text-ink">
            <IoCheckmark size={14} aria-hidden />
            Keeping this one
          </span>
        ) : (
          <button
            type="button"
            onClick={onKeep}
            disabled={disabled}
            className={OUTLINE_BUTTON}
          >
            Keep this one
          </button>
        )}
        {event.source_url && (
          <a
            href={event.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink underline decoration-ink/20 underline-offset-2 outline-none interactive-focus rounded-sm"
          >
            Source post
            <IoOpenOutline size={12} aria-hidden />
          </a>
        )}
      </div>
    </article>
  );
}

function formatList(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}
