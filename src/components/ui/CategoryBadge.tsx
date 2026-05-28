import type { EventCategory } from "@/types/event";

const CATEGORY_STYLES: Record<
  EventCategory,
  { label: string; cls: string }
> = {
  club: { label: "Club", cls: "bg-highlander/10 text-highlander" },
  academic: { label: "Academic", cls: "bg-leaf/12 text-deep-leaf" },
  social: { label: "Social", cls: "bg-coral/12 text-deep-coral" },
  career: { label: "Career", cls: "bg-ink/10 text-ink" },
  sports: { label: "Sports", cls: "bg-sky/12 text-deep-sky" },
  arts: { label: "Arts", cls: "bg-plum/12 text-deep-plum" },
  community: { label: "Community", cls: "bg-sage/15 text-deep-sage" },
  free_food: { label: "Free Food", cls: "bg-gold/15 text-deep-gold" },
};

export function CategoryBadge({
  category,
  variant = "default",
}: {
  category: EventCategory;
  variant?: "default" | "overlay";
}) {
  const style = CATEGORY_STYLES[category];
  const cls =
    variant === "overlay"
      ? "bg-white/15 text-white backdrop-blur-sm"
      : style.cls;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-medium tracking-[0.01em] ${cls}`}
    >
      {style.label}
    </span>
  );
}

export { CATEGORY_STYLES };
