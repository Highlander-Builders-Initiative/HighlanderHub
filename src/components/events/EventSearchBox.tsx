"use client";

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { searchClubs, type Club } from "@/lib/clubs";
import { ClubAvatar } from "@/components/ui/ClubAvatar";

type Props = {
  query: string;
  clubs: Club[];
  onQueryChange: (next: string) => void;
};

const DROPDOWN_LIMIT = 8;

export function EventSearchBox({ query, clubs: allClubs, onQueryChange }: Props) {
  const inputId = useId();
  const listboxId = `${inputId}-clubs`;
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  // Track the query string most recently confirmed by clicking/Enter on a club
  // suggestion, so that selection doesn't immediately re-open the dropdown
  // from the resulting onChange/effect.
  const justSelectedRef = useRef<string | null>(null);

  const clubs = useMemo(
    () => searchClubs(query, DROPDOWN_LIMIT, allClubs),
    [query, allClubs]
  );

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: MouseEvent) {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setActiveIndex(-1);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- clamp highlight when the suggestion list shrinks
    if (clubs.length === 0) setActiveIndex(-1);
    else if (activeIndex >= clubs.length) setActiveIndex(clubs.length - 1);
  }, [clubs, activeIndex]);


  const selectClub = useCallback(
    (club: Club) => {
      justSelectedRef.current = club.handle;
      onQueryChange(club.handle);
      setOpen(false);
      setActiveIndex(-1);
      inputRef.current?.blur();
    },
    [onQueryChange]
  );

  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (!open) {
          setOpen(true);
          setActiveIndex(0);
          return;
        }
        if (clubs.length === 0) return;
        setActiveIndex((i) => (i + 1) % clubs.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (!open || clubs.length === 0) return;
        setActiveIndex((i) => (i <= 0 ? clubs.length - 1 : i - 1));
      } else if (e.key === "Enter") {
        if (open && activeIndex >= 0 && clubs[activeIndex]) {
          e.preventDefault();
          selectClub(clubs[activeIndex]);
        }
      } else if (e.key === "Escape") {
        if (open) {
          e.preventDefault();
          setOpen(false);
          setActiveIndex(-1);
        }
      } else if (e.key === "Tab") {
        setOpen(false);
        setActiveIndex(-1);
      }
    },
    [open, clubs, activeIndex, selectClub]
  );

  const showDropdown = open && clubs.length > 0;
  const activeClub =
    showDropdown && activeIndex >= 0 ? clubs[activeIndex] : undefined;
  const activeOptionId =
    activeClub ? `${listboxId}-opt-${activeClub.handle}` : undefined;

  // No `relative` on the container: the dropdown anchors to the filter bar's
  // capsule (the nearest positioned ancestor) so it spans the whole bar.
  return (
    <div ref={containerRef} className="min-w-0 flex-1">
      <label htmlFor={inputId} className="sr-only">
        Search events and clubs
      </label>
      <div className="relative">
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="pointer-events-none absolute left-0 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
        >
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        <input
          ref={inputRef}
          id={inputId}
          type="search"
          value={query}
          onChange={(e) => {
            justSelectedRef.current = null;
            onQueryChange(e.target.value);
            setOpen(e.target.value.trim().length > 0);
          }}
          onKeyDown={onKeyDown}
          placeholder="Search events, or pick a club"
          autoComplete="off"
          aria-describedby="event-filter-summary"
          role="combobox"
          aria-expanded={showDropdown}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={activeOptionId}
          // The capsule draws the focus ring (.liquid-glass in globals.css).
          className="h-9 w-full text-ellipsis bg-transparent pl-7 pr-2 text-sm text-ink outline-none placeholder:text-muted"
        />
      </div>

      {showDropdown && (
        <div
          // Solid, not glass: the capsule's backdrop-filter walls off the
          // feed, so a blur here would only ghost the cards through.
          className="absolute inset-x-0 top-full z-30 mt-2 overflow-hidden rounded-3xl bg-canvas p-1.5 shadow-[0_0_0_1px_rgba(15,17,21,0.07),0_18px_44px_rgba(15,17,21,0.12)]"
          // Block the input's blur from firing before the row's onClick can
          // run — pointer-down on the dropdown container would otherwise
          // collapse the list mid-click.
          onMouseDown={(e) => e.preventDefault()}
        >
          <div className="px-3 pb-1 pt-1.5 text-[12px] font-medium text-muted">
            Clubs
          </div>
          <ul
            id={listboxId}
            role="listbox"
            aria-label="Clubs"
            className="max-h-[320px] overflow-y-auto"
          >
            {clubs.map((club, idx) => {
              const isActive = idx === activeIndex;
              return (
                <li
                  key={club.handle}
                  id={`${listboxId}-opt-${club.handle}`}
                  role="option"
                  aria-selected={isActive}
                  onMouseEnter={() => setActiveIndex(idx)}
                  onClick={() => selectClub(club)}
                  className={`flex cursor-pointer items-center gap-3 rounded-[18px] px-3 py-2 ${
                    isActive ? "bg-ink/[0.05]" : ""
                  }`}
                >
                  <ClubAvatar handle={club.handle} name={club.label} size={32} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[14px] font-medium text-ink">
                      {club.label}
                    </span>
                    <span className="block truncate text-[12px] text-muted">
                      @{club.handle}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
