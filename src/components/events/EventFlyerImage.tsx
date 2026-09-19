"use client";

import Image from "next/image";
import type { CSSProperties } from "react";
import { isOptimizableFlyerHost } from "@/lib/events/flyer-hosts";

type EventFlyerImageProps = {
  src: string;
  alt: string;
  fill?: boolean;
  /** Intrinsic-size hints for non-fill images; CSS decides the rendered size. */
  width?: number;
  height?: number;
  sizes?: string;
  className?: string;
  style?: CSSProperties;
  priority?: boolean;
  onLoad?: (img: HTMLImageElement) => void;
  onError?: () => void;
};

/**
 * Optimizes flyers from allowlisted CDNs via next/image; serves arbitrary
 * user-supplied hosts through a plain <img> (CSP img-src allows any HTTPS).
 * Keeping the optimizer allowlist closed avoids an open server-side proxy.
 */
export function EventFlyerImage({
  src,
  alt,
  fill = false,
  width,
  height,
  sizes,
  className,
  style,
  priority,
  onLoad,
  onError,
}: EventFlyerImageProps) {
  if (isOptimizableFlyerHost(src)) {
    return (
      <Image
        src={src}
        alt={alt}
        fill={fill}
        width={fill ? undefined : width}
        height={fill ? undefined : height}
        sizes={sizes}
        className={className}
        style={style}
        priority={priority}
        onLoad={onLoad ? (event) => onLoad(event.currentTarget) : undefined}
        onError={onError}
      />
    );
  }

  const imgClassName = fill
    ? `absolute inset-0 h-full w-full ${className ?? ""}`.trim()
    : className;

  // React re-attaches an inline ref on every render, so report each loaded
  // source once, as next/image does.
  const reportLoad = (img: HTMLImageElement) => {
    if (reportedSrc.get(img) === img.currentSrc) return;
    reportedSrc.set(img, img.currentSrc);
    onLoad?.(img);
  };

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      // A server-rendered flyer can finish (or fail) before hydration, when
      // React's handlers are not listening yet; next/image covers this too.
      ref={(img) => {
        if (!img?.complete) return;
        if (img.naturalWidth > 0) reportLoad(img);
        else onError?.();
      }}
      src={src}
      alt={alt}
      width={fill ? undefined : width}
      height={fill ? undefined : height}
      className={imgClassName}
      style={style}
      loading={priority ? "eager" : "lazy"}
      decoding="async"
      onLoad={(event) => reportLoad(event.currentTarget)}
      onError={onError}
    />
  );
}

const reportedSrc = new WeakMap<HTMLImageElement, string>();
