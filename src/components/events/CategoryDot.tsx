import { CATEGORY_RAIL } from "@/lib/category-colors";
import type { CampusEvent } from "@/types/event";

export function CategoryDot({
  category,
  className = "h-1.5 w-1.5 rounded-full",
}: {
  category: CampusEvent["category"];
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={`shrink-0 ${className} ${CATEGORY_RAIL[category] ?? "bg-ink"}`}
    />
  );
}
