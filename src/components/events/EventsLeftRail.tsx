"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { SITE_NAV_LINKS } from "@/lib/site-nav";
import { EventCategoryFilter } from "./EventCategoryFilter";
import type { CategoryValue } from "./events-filters";

type Props = {
  category: CategoryValue;
  onCategoryChange: (cat: CategoryValue) => void;
  counts: Map<CategoryValue, number>;
};

export function EventsLeftRail({ category, onCategoryChange, counts }: Props) {
  const pathname = usePathname();

  return (
    <div>
      <nav aria-label="Site" className="flex flex-col gap-0.5">
        {SITE_NAV_LINKS.map((link) => {
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

      <p className="px-2.5 pb-2 text-[12px] font-medium text-muted">Topics</p>

      <EventCategoryFilter
        layout="rail"
        category={category}
        onCategoryChange={onCategoryChange}
        counts={counts}
      />
    </div>
  );
}
