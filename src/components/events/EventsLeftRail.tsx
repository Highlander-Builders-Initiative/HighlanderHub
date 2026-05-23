"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { EventCategory } from "@/types/event";
import { CATEGORY_RAIL } from "@/lib/category-colors";
import { CATEGORIES } from "./events-filters";

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/events", label: "Events" },
  { href: "/about", label: "About" },
  { href: "/submit", label: "Submit" },
] as const;

type Props = {
  category: EventCategory | "all";
  onCategoryChange: (cat: EventCategory | "all") => void;
  counts: Map<EventCategory | "all", number>;
};

export function EventsLeftRail({ category, onCategoryChange, counts }: Props) {
  const pathname = usePathname();

  return (
    <div>
      <nav aria-label="Site" className="flex flex-col gap-0.5">
        {NAV_LINKS.map((link) => {
          const active =
            link.href === "/"
              ? pathname === "/"
              : pathname === link.href || pathname?.startsWith(`${link.href}/`);
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={[
                "interactive-focus rounded-md px-2.5 py-1.5 text-[14px] transition-colors",
                active
                  ? "bg-ink/[0.05] font-medium text-ink"
                  : "text-muted hover:bg-ink/[0.03] hover:text-ink",
              ].join(" ")}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>

      <div className="my-5 h-px bg-ink/10" />

      <p className="px-2.5 pb-2 text-[12px] font-medium text-muted">Browse</p>

      <div
        className="flex flex-col gap-0.5"
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
                "interactive-focus flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-[14px] transition-colors",
                active
                  ? "bg-ink/[0.05] font-medium text-ink"
                  : "text-ink/85 hover:bg-ink/[0.03] hover:text-ink",
              ].join(" ")}
            >
              <span
                aria-hidden
                className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotClass}`}
              />
              <span className="flex-1">{c.label}</span>
              <span
                className={[
                  "font-mono text-[11px] tabular-nums",
                  active ? "text-ink/70" : "text-muted/70",
                ].join(" ")}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
