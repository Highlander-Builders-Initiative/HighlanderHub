import type { EventCategory } from "@/types/event";

const CATEGORY_STYLES: Record<EventCategory, { label: string; bg: string; fg: string }> = {
  club: { label: "Club", bg: "bg-clay", fg: "text-bone" },
  academic: { label: "Academic", bg: "bg-olive", fg: "text-bone" },
  social: { label: "Social", bg: "bg-citrus", fg: "text-ink" },
  career: { label: "Career", bg: "bg-ink", fg: "text-bone" },
  sports: { label: "Sports", bg: "bg-rust", fg: "text-bone" },
  arts: { label: "Arts", bg: "bg-sky", fg: "text-bone" },
  community: { label: "Community", bg: "bg-sand", fg: "text-ink" },
  free_food: { label: "Free Food", bg: "bg-citrus", fg: "text-ink" },
};

export function CategoryBadge({ category }: { category: EventCategory }) {
  const style = CATEGORY_STYLES[category];
  return (
    <span
      className={`font-mono text-[10px] uppercase tracking-widest px-2 py-1 ${style.bg} ${style.fg}`}
    >
      {style.label}
    </span>
  );
}

export { CATEGORY_STYLES };
