"use client";

import { type CSSProperties, useState, useSyncExternalStore } from "react";
import { EventFlyerImage } from "@/components/events/EventFlyerImage";

type FlyerPosterProps = {
  src: string;
  alt: string;
  sizes: string;
  /** Edge, fill and radius. Bounds come from --flyer-max-w / --flyer-max-h
   *  on the slot around it. */
  className?: string;
  priority?: boolean;
  /** When the flyer's shape only arrives after first paint, keep the
   *  placeholder's space and center the flyer in it, so content below never
   *  jumps. For heroes that sit above the text. */
  reserveSpace?: boolean;
  onError?: () => void;
};

// Shapes this session has already loaded. A flyer opened from its feed card
// already knows its shape, so the detail view reserves the right space.
const knownRatios = new Map<string, number>();
const subscribe = () => () => {};

const ratioStyle = (ratio: number | null) =>
  ratio ? ({ "--flyer-ratio": ratio } as CSSProperties) : undefined;

/**
 * A flyer shown whole, at its own shape (see .flyer-poster in globals.css).
 * The caller's slot keeps rows and rails consistent; the flyer is never
 * cropped to fit it.
 */
export function FlyerPoster({
  src,
  alt,
  sizes,
  className = "",
  priority,
  reserveSpace = false,
  onError,
}: FlyerPosterProps) {
  const [loaded, setLoaded] = useState<{
    src: string;
    ratio: number | null;
  } | null>(null);
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  // Hydration renders the server's null, then the client's remembered shape.
  const knownRatio = useSyncExternalStore(
    subscribe,
    () => knownRatios.get(src) ?? null,
    () => null
  );
  const [knownAtFirstPaint] = useState(knownRatio !== null);
  const ownRatio = loaded?.src === src ? loaded.ratio : null;
  const ratio = ownRatio ?? knownRatio;
  // The slot shimmers until the flyer paints over it, and goes still if the
  // flyer fails, so a dead link never reads as still loading.
  const pending = loaded?.src !== src && failedSrc !== src;

  // The frame (className) is drawn on this box, which takes the flyer's shape;
  // the image fills it and fades in over the placeholder.
  const image = (
    <span
      className={`flyer-poster relative block overflow-hidden ${
        pending ? "skeleton" : ""
      } ${className}`}
      style={ratioStyle(ratio)}
    >
      <EventFlyerImage
        src={src}
        alt={alt}
        sizes={sizes}
        width={1000}
        height={1250}
        priority={priority}
        className="absolute inset-0 h-full w-full object-contain"
        onLoad={(img) => {
          const next =
            img.naturalWidth && img.naturalHeight
              ? img.naturalWidth / img.naturalHeight
              : null;
          if (next) knownRatios.set(src, next);
          setLoaded((prev) =>
            prev?.src === src && prev.ratio === next ? prev : { src, ratio: next }
          );
        }}
        onError={() => {
          setFailedSrc(src);
          onError?.();
        }}
      />
    </span>
  );

  if (!reserveSpace) return image;

  // The stage matches the flyer, except when the shape arrived late: then it
  // keeps the placeholder's size that was already painted.
  const stageRatio = ownRatio !== null && !knownAtFirstPaint ? null : ratio;
  return (
    <span
      className="flyer-poster flex items-center justify-center"
      style={ratioStyle(stageRatio)}
    >
      {image}
    </span>
  );
}
