"use client";

import { useEffect, useRef } from "react";
import type { EventCategory } from "@/types/event";
import { CATEGORY_RAIL } from "@/lib/category-colors";
import { EventsMiniCalendar } from "./EventsMiniCalendar";
import {
  CATEGORIES,
  DAY_WINDOWS,
  type CategoryValue,
  type DayWindow,
} from "./events-filters";

type Props = {
  open: boolean;
  onClose: () => void;
  category: CategoryValue;
  onCategoryChange: (cat: CategoryValue) => void;
  counts: Map<CategoryValue, number>;
  dayWindow: DayWindow;
  onDayWindowChange: (next: DayWindow) => void;
  cursor: string;
  onCursorChange: (next: string) => void;
  todayKey: string;
  selectedKey: string;
  onSelect: (dayKey: string) => void;
  categoriesByDay: Map<string, EventCategory[]>;
  onClear: () => void;
  hasActiveFilters: boolean;
  resultCount: number;
};

export function EventsMobileFilterSheet({
  open,
  onClose,
  category,
  onCategoryChange,
  counts,
  dayWindow,
  onDayWindowChange,
  cursor,
  onCursorChange,
  todayKey,
  selectedKey,
  onSelect,
  categoriesByDay,
  onClear,
  hasActiveFilters,
  resultCount,
}: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Filter events"
      className="fixed inset-0 z-50 flex flex-col justify-end lg:hidden"
    >
      {/* Backdrop */}
      <button
        type="button"
        aria-label="Close filters"
        onClick={onClose}
        className="absolute inset-0 bg-ink/40 transition-opacity"
        tabIndex={-1}
      />

      {/* Sheet */}
      <div
        className="relative flex max-h-[88vh] flex-col rounded-t-2xl bg-canvas shadow-[0_-12px_40px_rgba(15,17,21,0.18)]"
        style={{
          animation:
            "sheet-up 280ms cubic-bezier(0.16, 1, 0.3, 1) both",
        }}
      >
        <div className="flex items-center justify-between border-b border-ink/10 px-5 py-3">
          <h2 className="font-display text-lg font-semibold tracking-[-0.015em] text-ink">
            Filter events
          </h2>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close filters"
            className="interactive-focus inline-flex h-9 w-9 items-center justify-center rounded-md text-muted transition-colors hover:bg-ink/[0.04] hover:text-ink"
          >
            <svg
              aria-hidden
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-5 w-5"
            >
              <path d="M6 6l12 12M6 18 18 6" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5">
          <div>
            <p className="pb-2 text-[12px] font-medium text-muted">Browse</p>
            <div
              className="grid grid-cols-2 gap-1.5"
              role="group"
              aria-label="Filter events by category"
            >
              {CATEGORIES.map((c) => {
                const active = category === c.value;
                const count = counts.get(c.value) ?? 0;
                const dotClass =
                  c.value === "all" ? "bg-ink/30" : CATEGORY_RAIL[c.value];
                return (
                  <button
                    type="button"
                    key={c.value}
                    onClick={() => onCategoryChange(c.value)}
                    aria-pressed={active}
                    className={[
                      "interactive-focus flex items-center gap-2 rounded-md border px-3 py-2 text-left text-[14px] transition-colors",
                      active
                        ? "border-ink bg-ink/[0.04] font-medium text-ink"
                        : "border-ink/15 text-ink/85 hover:border-ink",
                    ].join(" ")}
                  >
                    <span
                      aria-hidden
                      className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotClass}`}
                    />
                    <span className="flex-1">{c.label}</span>
                    <span className="font-mono text-[11px] tabular-nums text-muted/80">
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-6">
            <p className="pb-2 text-[12px] font-medium text-muted">When</p>
            <div
              className="flex flex-wrap gap-1.5"
              role="group"
              aria-label="Filter events by time window"
            >
              {DAY_WINDOWS.map((w) => {
                const active = dayWindow === w.value;
                return (
                  <button
                    type="button"
                    key={w.value}
                    onClick={() => onDayWindowChange(w.value)}
                    aria-pressed={active}
                    className={[
                      "interactive-focus inline-flex min-h-9 items-center rounded-full border px-3.5 py-1 text-[13px] transition-colors",
                      active
                        ? "border-ink bg-ink text-canvas"
                        : "border-ink/15 bg-canvas text-ink hover:border-ink",
                    ].join(" ")}
                  >
                    {w.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-6">
            <EventsMiniCalendar
              cursor={cursor}
              onCursorChange={onCursorChange}
              todayKey={todayKey}
              selectedKey={selectedKey}
              onSelect={onSelect}
              categoriesByDay={categoriesByDay}
            />
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-ink/10 px-5 py-3">
          <button
            type="button"
            onClick={onClear}
            disabled={!hasActiveFilters}
            className="interactive-focus text-[14px] font-medium text-ink underline-offset-4 transition-opacity hover:underline disabled:opacity-40 disabled:no-underline"
          >
            Clear filters
          </button>
          <button
            type="button"
            onClick={onClose}
            className="interactive-focus inline-flex min-h-10 items-center rounded-lg bg-ink px-5 py-2 text-[14px] font-medium text-canvas transition-opacity hover:opacity-85"
          >
            Show {resultCount} {resultCount === 1 ? "event" : "events"}
          </button>
        </div>
      </div>

      <style jsx>{`
        @keyframes sheet-up {
          from {
            transform: translateY(100%);
            opacity: 0.5;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
}
