import type { EventCategory } from "@/types/event";
import { CATEGORY_PILL } from "@/lib/category-colors";

const pill = (category: EventCategory) =>
  `${CATEGORY_PILL[category].highlight} ${CATEGORY_PILL[category].text}`;

const CATEGORY_STYLES: Record<
  EventCategory,
  { label: string; cls: string }
> = {
  club: { label: "Club", cls: pill("club") },
  academic: { label: "Academic", cls: pill("academic") },
  social: { label: "Social", cls: pill("social") },
  career: { label: "Career", cls: pill("career") },
  sports: { label: "Sports", cls: pill("sports") },
  arts: { label: "Arts", cls: pill("arts") },
  community: { label: "Community", cls: pill("community") },
  free_food: { label: "Free Food", cls: pill("free_food") },
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
