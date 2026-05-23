"use client";

import { useEffect, useRef } from "react";
import type { EventCategory } from "@/types/event";
import { EventCategoryFilter } from "./EventCategoryFilter";
import { EventDayWindowFilter } from "./EventDayWindowFilter";
import { EventsMiniCalendar } from "./EventsMiniCalendar";
import { type CategoryValue, type DayWindow } from "./events-filters";

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
  isCalendarLoading: boolean;
  onClear: () => void;
  hasActiveFilters: boolean;
  resultCount: number;
};

const FOCUSABLE_SELECTOR = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

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
  isCalendarLoading,
  onClear,
  hasActiveFilters,
  resultCount,
}: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const lastActiveElementRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;

    lastActiveElementRef.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusables = () =>
      Array.from(panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? [])
        .filter((el) => !el.hasAttribute("disabled") && el.tabIndex !== -1);

    const first = focusables()[0] ?? closeRef.current;
    first?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key !== "Tab") return;

      const tabbables = focusables();
      if (tabbables.length === 0) {
        e.preventDefault();
        closeRef.current?.focus();
        return;
      }

      const firstTabbable = tabbables[0];
      const lastTabbable = tabbables[tabbables.length - 1];
      const active = document.activeElement as HTMLElement | null;

      if (e.shiftKey) {
        if (!active || active === firstTabbable || !panelRef.current?.contains(active)) {
          e.preventDefault();
          lastTabbable.focus();
        }
      } else if (!active || active === lastTabbable || !panelRef.current?.contains(active)) {
        e.preventDefault();
        firstTabbable.focus();
      }
    };
    window.addEventListener("keydown", onKey);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
      lastActiveElementRef.current?.focus?.();
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
        ref={panelRef}
        tabIndex={-1}
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
            <EventCategoryFilter
              layout="grid"
              category={category}
              onCategoryChange={onCategoryChange}
              counts={counts}
            />
          </div>

          <div className="mt-6">
            <p className="pb-2 text-[12px] font-medium text-muted">When</p>
            <EventDayWindowFilter
              layout="sheet"
              dayWindow={dayWindow}
              onDayWindowChange={onDayWindowChange}
            />
          </div>

          <div className="mt-6">
            <EventsMiniCalendar
              cursor={cursor}
              onCursorChange={onCursorChange}
              todayKey={todayKey}
              selectedKey={selectedKey}
              onSelect={onSelect}
              categoriesByDay={categoriesByDay}
              isLoading={isCalendarLoading}
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
