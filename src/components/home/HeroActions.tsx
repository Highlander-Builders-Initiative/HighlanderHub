"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useRef, type FormEvent } from "react";
import { FiSearch, FiArrowRight, FiUsers, FiCalendar, FiGift, FiBriefcase, FiMusic } from "react-icons/fi";

const CLUB_CATEGORIES_PREVIEW = [
  { label: "Academic & Professional", count: 154, href: "/events?cat=academic" },
  { label: "Recreational & Sports", count: 70, href: "/events?cat=sports" },
  { label: "Service & Community", count: 57, href: "/events?cat=community" },
  { label: "Cultural & Identity", count: 50, href: "/events?cat=social" },
  { label: "Arts & Performance", count: 45, href: "/events?cat=arts" },
  { label: "All 640+ Student Orgs", count: 647, href: "/events?cat=club" },
];

const QUICK_FILTERS = [
  { label: "Free Food", icon: FiGift, href: "/events?cat=free_food", bg: "hover:border-amber-400/40 hover:bg-amber-50/60 text-amber-900 dark:text-amber-300" },
  { label: "Clubs & Orgs", icon: FiUsers, href: "/events?cat=club", bg: "hover:border-blue-400/40 hover:bg-blue-50/60 text-blue-900 dark:text-blue-300" },
  { label: "Career & Fairs", icon: FiBriefcase, href: "/events?cat=career", bg: "hover:border-emerald-400/40 hover:bg-emerald-50/60 text-emerald-900 dark:text-emerald-300" },
  { label: "Arts & Shows", icon: FiMusic, href: "/events?cat=arts", bg: "hover:border-purple-400/40 hover:bg-purple-50/60 text-purple-900 dark:text-purple-300" },
  { label: "Calendar View", icon: FiCalendar, href: "/events", bg: "hover:border-slate-400/40 hover:bg-slate-50/60 text-slate-800 dark:text-slate-300" },
];

export function HeroActions({ upcomingCount }: { upcomingCount?: number | null }) {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [clubsDropdownOpen, setClubsDropdownOpen] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const handleSearch = (e: FormEvent) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (q) {
      router.push(`/events?q=${encodeURIComponent(q)}`);
    } else {
      router.push("/events");
    }
  };

  const handleMouseEnter = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setClubsDropdownOpen(true);
  };

  const handleMouseLeave = () => {
    timeoutRef.current = setTimeout(() => {
      setClubsDropdownOpen(false);
    }, 150);
  };

  return (
    <div className="mt-8 flex flex-col items-center gap-5 sm:mt-10">
      {/* Primary Button Row (Berkeley Goggles style) */}
      <div className="relative flex flex-wrap items-center justify-center gap-3.5">
        {/* Explore Clubs with Hover Dropdown */}
        <div
          className="relative"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          <Link
            href="/events?cat=club"
            className="group inline-flex items-center gap-2 rounded-full border border-blue-600/30 bg-blue-50/50 px-6 py-2.5 text-sm font-medium text-blue-700 backdrop-blur-sm transition-all duration-200 hover:border-blue-600 hover:bg-blue-600/10 hover:text-blue-800 hover:shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <FiUsers className="h-4 w-4 text-blue-600 transition-transform group-hover:scale-110" />
            <span>Explore 640+ Clubs</span>
          </Link>

          {/* Hover Reveal Dropdown */}
          {clubsDropdownOpen && (
            <div className="absolute left-1/2 top-full z-40 mt-2 w-72 -translate-x-1/2 rounded-2xl border border-slate-200/80 bg-white/95 p-3.5 shadow-xl backdrop-blur-xl animate-in fade-in zoom-in-95 duration-150">
              <div className="mb-2 border-b border-slate-100 pb-2 px-1 text-[11px] font-semibold uppercase tracking-wider text-slate-600">
                Discover UCR Organizations
              </div>
              <ul className="space-y-1">
                {CLUB_CATEGORIES_PREVIEW.map((item) => (
                  <li key={item.label}>
                    <Link
                      href={item.href}
                      className="flex items-center justify-between rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-blue-50 hover:text-blue-700"
                    >
                      <span>{item.label}</span>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-700">
                        {item.count}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Browse Events Button */}
        <Link
          href="/events"
          className="group inline-flex items-center gap-2 rounded-full bg-blue-600 px-6 py-2.5 text-sm font-medium text-white shadow-sm transition-all duration-200 hover:bg-blue-700 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          <span>Browse Events</span>
          {upcomingCount ? (
            <span className="rounded-full bg-white/20 px-2 py-0.5 text-[11px] font-semibold text-white">
              {upcomingCount}
            </span>
          ) : null}
          <FiArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
        </Link>
      </div>

      {/* Interactive Quick Search Bar */}
      <form
        onSubmit={handleSearch}
        className="group relative w-full max-w-lg transition-all duration-200"
      >
        <div className="relative flex items-center rounded-full border border-slate-200 bg-white/90 shadow-sm backdrop-blur-md transition-all duration-200 hover:border-slate-300 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:shadow-md">
          <FiSearch className="ml-4 h-4 w-4 shrink-0 text-slate-600 group-focus-within:text-blue-600" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search 640+ clubs, free food, career fairs..."
            aria-label="Search events and campus clubs"
            className="w-full bg-transparent px-3 py-2.5 text-sm text-slate-900 placeholder-slate-600 focus:outline-none"
          />
          <button
            type="submit"
            aria-label="Submit search"
            className="mr-2 inline-flex h-7 items-center justify-center rounded-full bg-slate-100 px-2.5 text-xs font-medium text-slate-600 transition-colors hover:bg-blue-600 hover:text-white"
          >
            <span className="hidden sm:inline">Find ↵</span>
            <span className="sm:hidden">↵</span>
          </button>
        </div>
      </form>

      {/* Scannable Quick Category Chips */}
      <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
        {QUICK_FILTERS.map((chip) => {
          const Icon = chip.icon;
          return (
            <Link
              key={chip.label}
              href={chip.href}
              className={`inline-flex items-center gap-1.5 rounded-full border border-slate-200/80 bg-white/80 px-3 py-1 text-xs font-medium backdrop-blur-sm transition-all duration-150 ${chip.bg}`}
            >
              <Icon className="h-3.5 w-3.5 opacity-70" />
              <span>{chip.label}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
