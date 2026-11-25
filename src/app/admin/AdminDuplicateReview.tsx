"use client";

import React, {
  useEffect,
  useEffectEvent,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { IoCheckmarkOutline, IoPencilOutline } from "react-icons/io5";
import clsx from "clsx";
import { FlyerPoster } from "@/components/events/FlyerPoster";
import { formatDayShort, formatTime, formatTimeRange } from "@/lib/dates";
import { eventRowToCampusEvent } from "@/lib/events/map-event-row";
import { RowLink, ADMIN_TAG } from "./AdminLiveEventRow";
import {
  type MergeFieldChoice,
  defaultMergeTakes,
  duplicateMergeChanges,
  mergeFieldOptions,
  mergeLocksListing,
} from "./duplicate-merge";
import {
  type AdminActionError,
  type AdminPendingAction,
  actionErrorFor,
} from "./pending-action";
import {
  type AdminEventRow,
  type DuplicateReviewPair,
  duplicatePairKey,
} from "./types";

const OUTLINE_BUTTON =
  "min-h-9 px-3 border border-ink/10 hover:bg-ink/5 text-muted hover:text-ink rounded-md outline-none interactive-focus press inline-flex items-center justify-center gap-1.5 text-xs font-semibold disabled:opacity-50";

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

const FIELD_LABELS: Record<MergeFieldChoice, string> = {
  starts_at: "Date & time",
  location: "Venue",
  ends_at: "End time",
  image_url: "Flyer",
  rsvp_url: "RSVP link",
};

function fieldValue(field: MergeFieldChoice, event: AdminEventRow): string {
  switch (field) {
    case "starts_at":
      return when(event);
    case "location":
      return event.location.trim() || "No venue";
    case "ends_at":
      return event.ends_at ? `Ends ${formatTime(event.ends_at)}` : "No end time";
    case "image_url":
      return event.image_url ? "Its flyer" : "No flyer";
    case "rsvp_url":
      if (!event.rsvp_url) return "No RSVP link";
      try {
        return new URL(event.rsvp_url).hostname.replace(/^www\./, "");
      } catch {
        return event.rsvp_url;
      }
  }
}

/** A pair's in-progress decision: which listing stays, which details move. */
type Choice = { keptId: string; takes: MergeFieldChoice[] };

// Keys typed into these still type; shortcuts wait for the admin to leave.
const TYPING = 'input:not([type="radio"]):not([type="checkbox"]), textarea, select, [contenteditable="true"]';

export function AdminDuplicateReview({
  pairs,
  queueError,
  feedPositionById,
  pendingAction,
  actionError,
  onMerge,
  onDistinct,
  onEdit,
}: {
  pairs: DuplicateReviewPair[];
  queueError: string | null;
  feedPositionById: Map<string, number>;
  pendingAction: AdminPendingAction | null;
  actionError: AdminActionError | null;
  onMerge: (
    pairKey: string,
    kept: AdminEventRow,
    removed: AdminEventRow,
    takes: MergeFieldChoice[]
  ) => void;
  onDistinct: (pairKey: string, pair: DuplicateReviewPair) => void;
  onEdit: (event: AdminEventRow) => void;
}) {
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const cardRefs = useRef(new Map<string, HTMLLIElement>());
  // The pair to focus once the list re-renders without the one just decided.
  const pendingFocus = useRef<string | null>(null);

  const keys = useMemo(() => pairs.map(duplicatePairKey), [pairs]);
  const active = keys.includes(activeKey ?? "") ? activeKey : (keys[0] ?? null);
  const busy = pendingAction?.type === "merge" || pendingAction?.type === "distinct";

  // Focusing a card makes it the active pair (see onFocusCapture).
  const focusCard = (key: string) => {
    const card = cardRefs.current.get(key);
    if (!card) return;
    card.focus({ preventScroll: true });
    card.scrollIntoView({ block: "nearest", behavior: "smooth" });
  };

  useEffect(() => {
    const key = pendingFocus.current;
    pendingFocus.current = null;
    if (key) focusCard(key);
  }, [keys]);

  // A decision that failed brings its pair back; take the admin to it.
  const failedKey =
    actionError &&
    (actionError.action.type === "merge" || actionError.action.type === "distinct")
      ? actionError.action.id
      : null;
  useEffect(() => {
    if (failedKey && keys.includes(failedKey)) focusCard(failedKey);
  }, [failedKey, keys]);

  const choose = (key: string, pair: DuplicateReviewPair, keptId: string) => {
    const kept = keptId === pair.first.id ? pair.first : pair.second;
    const removed = kept === pair.first ? pair.second : pair.first;
    setChoices((all) => ({
      ...all,
      [key]: { keptId, takes: defaultMergeTakes(kept, removed) },
    }));
  };
  const cancel = (key: string) =>
    setChoices((all) => {
      const next = { ...all };
      delete next[key];
      return next;
    });
  const setTake = (key: string, field: MergeFieldChoice, take: boolean) =>
    setChoices((all) => {
      const choice = all[key];
      if (!choice) return all;
      const takes = choice.takes.filter((f) => f !== field);
      return { ...all, [key]: { ...choice, takes: take ? [...takes, field] : takes } };
    });

  // After a decision, the next pair (or the previous, at the end) takes over.
  const moveOnFrom = (key: string) => {
    const index = keys.indexOf(key);
    const next = keys[index + 1] ?? keys[index - 1] ?? null;
    setActiveKey(next);
    pendingFocus.current = next;
  };
  const merge = (key: string, pair: DuplicateReviewPair) => {
    const choice = choices[key];
    if (!choice || busy) return;
    const kept = choice.keptId === pair.first.id ? pair.first : pair.second;
    const removed = kept === pair.first ? pair.second : pair.first;
    moveOnFrom(key);
    onMerge(key, kept, removed, choice.takes);
  };
  const distinct = (key: string, pair: DuplicateReviewPair) => {
    if (busy) return;
    moveOnFrom(key);
    onDistinct(key, pair);
  };

  const onShortcut = useEffectEvent((e: KeyboardEvent) => {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || busy || !active) return;
    const target = e.target instanceof Element ? e.target : null;
    if (target?.closest(TYPING) || document.querySelector("dialog[open]")) return;
    const pair = pairs[keys.indexOf(active)];
    if (!pair) return;

    if (e.key === "1" || e.key === "2") {
      choose(active, pair, (e.key === "1" ? pair.first : pair.second).id);
    } else if (e.key === "d" || e.key === "D") {
      distinct(active, pair);
    } else if (e.key === "Escape" && choices[active]) {
      cancel(active);
    } else if (e.key === "Enter" && choices[active] && !target?.closest("button, a")) {
      merge(active, pair);
    } else {
      return;
    }
    e.preventDefault();
  });
  useEffect(() => {
    const listener = (e: KeyboardEvent) => onShortcut(e);
    document.addEventListener("keydown", listener);
    return () => document.removeEventListener("keydown", listener);
  }, []);

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
          <p className="text-[0.6875rem] text-muted tabular-nums">
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
          <div className="space-y-1 text-xs text-muted font-sans max-w-[70ch]">
            <p>
              Keep one listing to merge a pair: the other comes off the site and its
              Instagram post points at the one you kept, so it won&apos;t come back.
              Pairs marked different both stay up and aren&apos;t flagged again.
            </p>
            <p className="hidden sm:block">
              Keys: <Kbd>1</Kbd> or <Kbd>2</Kbd> keeps the left or right listing,{" "}
              <Kbd>Enter</Kbd> merges, <Kbd>D</Kbd> marks them different,{" "}
              <Kbd>Esc</Kbd> cancels.
            </p>
          </div>
          <ol className="space-y-4">
            {pairs.map((pair, index) => {
              const key = keys[index];
              return (
                <DuplicatePairCard
                  key={key}
                  ref={(node) => {
                    if (node) cardRefs.current.set(key, node);
                    else cardRefs.current.delete(key);
                  }}
                  pair={pair}
                  position={index + 1}
                  isActive={key === active && pairs.length > 1}
                  feedPositionById={feedPositionById}
                  choice={choices[key] ?? null}
                  disabled={busy}
                  error={actionErrorFor(actionError, ["merge", "distinct"], key)}
                  onActivate={() => setActiveKey(key)}
                  onKeep={(keptId) => choose(key, pair, keptId)}
                  onTake={(field, take) => setTake(key, field, take)}
                  onCancel={() => cancel(key)}
                  onMerge={() => merge(key, pair)}
                  onDistinct={() => distinct(key, pair)}
                  onEdit={onEdit}
                />
              );
            })}
          </ol>
        </>
      )}
    </section>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border border-ink/15 bg-canvas px-1 font-sans text-[0.6875rem] text-ink">
      {children}
    </kbd>
  );
}

function DuplicatePairCard({
  ref,
  pair,
  position,
  isActive,
  feedPositionById,
  choice,
  disabled,
  error,
  onActivate,
  onKeep,
  onTake,
  onCancel,
  onMerge,
  onDistinct,
  onEdit,
}: {
  ref: React.Ref<HTMLLIElement>;
  pair: DuplicateReviewPair;
  position: number;
  isActive: boolean;
  feedPositionById: Map<string, number>;
  choice: Choice | null;
  disabled: boolean;
  error: string | null;
  onActivate: () => void;
  onKeep: (keptId: string) => void;
  onTake: (field: MergeFieldChoice, take: boolean) => void;
  onCancel: () => void;
  onMerge: () => void;
  onDistinct: () => void;
  onEdit: (event: AdminEventRow) => void;
}) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  const groupName = useId();
  const listings = [pair.first, pair.second];
  const kept = listings.find((event) => event.id === choice?.keptId) ?? null;
  const removed = kept ? listings.find((event) => event.id !== kept.id)! : null;
  // The other listing's date and time bring their own end with them.
  const options = (kept && removed ? mergeFieldOptions(kept, removed) : []).filter(
    (field) => !(field === "ends_at" && choice?.takes.includes("starts_at"))
  );
  // Free food, co-hosts and a signup requirement carry over on their own;
  // the field choices above already show the rest.
  const automatic =
    kept && removed && choice
      ? duplicateMergeChanges(kept, removed, choice.takes).additions.filter(
          (phrase) => !/^(date and time|venue|end time|flyer|RSVP link)/.test(phrase)
        )
      : [];

  useEffect(() => {
    if (choice?.keptId) confirmRef.current?.focus({ preventScroll: true });
  }, [choice?.keptId]);

  const differs = {
    title: normalized(pair.first.title) !== normalized(pair.second.title),
    when: when(pair.first) !== when(pair.second),
    where: normalized(pair.first.location) !== normalized(pair.second.location),
    host: normalized(hostLabel(pair.first)) !== normalized(hostLabel(pair.second)),
  };

  return (
    <li
      ref={ref}
      tabIndex={-1}
      aria-label={`Pair ${position}: ${pair.first.title} and ${pair.second.title}`}
      onFocusCapture={onActivate}
      onPointerDown={onActivate}
      className={clsx(
        "bg-canvas border rounded-xl shadow-card overflow-clip outline-none transition-colors",
        isActive ? "border-ink/40" : "border-ink/10"
      )}
    >
      <div className="grid sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-ink/10">
        {listings.map((event, index) => (
          <DuplicateListing
            key={event.id}
            side={index + 1}
            corner={index === 0 ? "rounded-t-xl sm:rounded-tr-none sm:rounded-tl-xl" : "sm:rounded-tr-xl"}
            event={event}
            feedIndex={feedPositionById.get(event.id)}
            differs={differs}
            outcome={kept === null ? null : event.id === kept.id ? "kept" : "removed"}
            disabled={disabled}
            onKeep={() => onKeep(event.id)}
            onEdit={() => onEdit(event)}
          />
        ))}
      </div>

      <div className="border-t border-ink/10 px-4 py-3 space-y-3">
        {kept && removed && choice ? (
          <div role="group" aria-label="Confirm merge" className="space-y-3">
            <p className="text-sm text-ink font-sans">
              Keep <span className="font-semibold">{kept.title}</span> and remove the
              other listing.
            </p>

            {options.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-muted font-sans">
                  Where the listings disagree, choose which detail to keep:
                </p>
                {options.map((field) => (
                  <div
                    key={field}
                    role="radiogroup"
                    aria-labelledby={`${groupName}-${field}`}
                    className="grid grid-cols-[5.5rem_1fr] items-start gap-x-3 gap-y-1 sm:grid-cols-[5.5rem_1fr_1fr]"
                  >
                    <span id={`${groupName}-${field}`} className="pt-1.5 text-xs text-muted font-sans">
                      {FIELD_LABELS[field]}
                    </span>
                    <TakeOption
                      name={`${groupName}-${field}-choice`}
                      label={fieldValue(field, kept)}
                      note="kept listing"
                      checked={!choice.takes.includes(field)}
                      onChange={() => onTake(field, false)}
                      disabled={disabled}
                    />
                    <TakeOption
                      name={`${groupName}-${field}-choice`}
                      label={fieldValue(field, removed)}
                      note="other listing"
                      checked={choice.takes.includes(field)}
                      onChange={() => onTake(field, true)}
                      disabled={disabled}
                      className="col-start-2 sm:col-start-auto"
                    />
                  </div>
                ))}
              </div>
            )}

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs text-muted font-sans">
                {automatic.length > 0
                  ? `The kept listing also takes the other's ${formatList(automatic)}.`
                  : options.length > 0
                    ? "Nothing else carries over."
                    : "The kept listing already has every detail the other one adds."}
                {mergeLocksListing(kept, removed, choice.takes) &&
                  " It will be locked so the next import keeps these choices."}
              </p>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={onCancel}
                  disabled={disabled}
                  className={OUTLINE_BUTTON}
                >
                  Cancel
                </button>
                <button
                  ref={confirmRef}
                  type="button"
                  onClick={onMerge}
                  disabled={disabled}
                  className="min-h-9 px-4 bg-ink text-canvas rounded-md hover:opacity-85 outline-none interactive-focus press inline-flex items-center justify-center text-xs font-semibold disabled:opacity-50"
                >
                  Merge listings
                </button>
              </div>
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
              disabled={disabled}
              className={OUTLINE_BUTTON}
            >
              Different events
            </button>
          </div>
        )}
        {error && (
          <p role="alert" className="text-xs text-deep-coral font-sans">
            {error}
          </p>
        )}
      </div>
    </li>
  );
}

function TakeOption({
  name,
  label,
  note,
  checked,
  onChange,
  disabled,
  className,
}: {
  name: string;
  label: string;
  note: string;
  checked: boolean;
  onChange: () => void;
  disabled: boolean;
  className?: string;
}) {
  return (
    <label
      className={clsx(
        "flex min-w-0 cursor-pointer items-start gap-2 rounded-md border px-2.5 py-1.5 text-xs font-sans transition-colors",
        checked ? "border-ink/40 bg-ink/[0.03] text-ink" : "border-ink/10 text-muted hover:border-ink/25",
        className
      )}
    >
      <input
        type="radio"
        name={name}
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-ink outline-none interactive-focus"
      />
      <span className="min-w-0 break-words">
        {label}
        <span className="block text-[0.6875rem] text-muted">{note}</span>
      </span>
    </label>
  );
}

function DuplicateListing({
  event,
  side,
  corner,
  feedIndex,
  differs,
  outcome,
  disabled,
  onKeep,
  onEdit,
}: {
  event: AdminEventRow;
  /** 1 for the left listing, 2 for the right: its keyboard shortcut. */
  side: number;
  /** The card corner this half sits in, so the kept outline follows it. */
  corner: string;
  feedIndex: number | undefined;
  differs: Record<"title" | "when" | "where" | "host", boolean>;
  outcome: "kept" | "removed" | null;
  disabled: boolean;
  onKeep: () => void;
  onEdit: () => void;
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
      <div className="flex items-center gap-2 text-[0.625rem] text-muted">
        {feedIndex !== undefined && (
          <span className="tabular-nums">#{feedIndex + 1}</span>
        )}
        <span className={`${ADMIN_TAG} bg-ink/5 border-ink/10 uppercase tracking-[0.08em]`}>
          {event.source}
        </span>
        {event.is_locked && (
          <span className={`${ADMIN_TAG} bg-gold/10 border-gold/20 text-deep-gold`}>
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
            className="flex h-[80px] w-[64px] shrink-0 items-center justify-center rounded border border-dashed border-ink/15 bg-surface text-[0.5625rem] text-muted text-center leading-tight"
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
            <IoCheckmarkOutline size={14} aria-hidden />
            Keeping this one
          </span>
        ) : (
          <button
            type="button"
            onClick={onKeep}
            disabled={disabled}
            aria-keyshortcuts={String(side)}
            className={OUTLINE_BUTTON}
          >
            Keep this one
            <span aria-hidden className="hidden sm:inline text-faint font-normal">
              {side}
            </span>
          </button>
        )}
        <button
          type="button"
          onClick={onEdit}
          disabled={disabled}
          aria-label={`Edit ${event.title}`}
          className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink outline-none interactive-focus rounded-sm active:opacity-70"
        >
          <IoPencilOutline size={12} aria-hidden />
          <span aria-hidden>Edit</span>
        </button>
        {campusEvent.sourceUrl && (
          <RowLink href={campusEvent.sourceUrl}>Source post</RowLink>
        )}
      </div>
    </article>
  );
}

function formatList(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}
