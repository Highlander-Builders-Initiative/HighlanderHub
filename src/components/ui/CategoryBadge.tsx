import type { EventCategory } from "@/types/event";

const CATEGORY_STYLES: Record<
  EventCategory,
  { label: string; cls: string }
> = {
  club: { label: "Club", cls: "bg-highlander/10 text-highlander" },
  academic: { label: "Academic", cls: "bg-leaf/10 text-[#1f6f4e]" },
  social: { label: "Social", cls: "bg-coral/10 text-[#b33a30]" },
  career: { label: "Career", cls: "bg-ink/10 text-ink" },
  sports: { label: "Sports", cls: "bg-sky/10 text-[#1d5fbf]" },
  arts: { label: "Arts", cls: "bg-coral/10 text-[#b33a30]" },
  community: { label: "Community", cls: "bg-leaf/10 text-[#1f6f4e]" },
  free_food: { label: "Free Food", cls: "bg-gold/15 text-[#8a6300]" },
};

export function CategoryBadge({ category }: { category: EventCategory }) {
  const style = CATEGORY_STYLES[category];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium tracking-[0.01em] ${style.cls}`}
    >
      {style.label}
    </span>
  );
}

export { CATEGORY_STYLES };
