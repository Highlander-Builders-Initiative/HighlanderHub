import type { CampusEvent } from "@/types/event";
import { FlyerTile, type FlyerTileSize } from "./FlyerTile";

// Asymmetric layout on desktop (4×4 grid), single column on mobile.
// Order matters: tile 0 is the hero of the mosaic.
const TILE_LAYOUTS: { size: FlyerTileSize; className: string }[] = [
  { size: "large", className: "md:col-span-2 md:row-span-3" },
  { size: "medium", className: "md:col-span-2 md:row-span-2" },
  { size: "small", className: "md:col-span-1 md:row-span-1" },
  { size: "small", className: "md:col-span-1 md:row-span-1" },
  { size: "wide", className: "md:col-span-2 md:row-span-1" },
  { size: "wide", className: "md:col-span-2 md:row-span-1" },
];

export function FlyerMosaic({ events }: { events: CampusEvent[] }) {
  // Prioritize events with images so the mosaic feels rich; backfill with
  // image-less events that will render as category-colored fallback tiles.
  const withImage = events.filter((e) => !!e.imageUrl);
  const withoutImage = events.filter((e) => !e.imageUrl);
  const ordered = [...withImage, ...withoutImage].slice(0, TILE_LAYOUTS.length);

  if (ordered.length === 0) {
    return (
      <div className="flex aspect-square items-center justify-center border border-dashed border-ink/15 bg-canvas p-8 text-sm text-muted">
        Nothing scheduled in the next few days. Check back soon.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 md:aspect-square md:grid-cols-4 md:grid-rows-4 md:gap-3">
      {ordered.map((event, i) => (
        <FlyerTile
          key={event.id}
          event={event}
          size={TILE_LAYOUTS[i].size}
          className={TILE_LAYOUTS[i].className}
          enterDelayMs={120 + i * 70}
        />
      ))}
    </div>
  );
}
