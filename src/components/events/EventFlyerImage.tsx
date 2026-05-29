"use client";

import Image from "next/image";
import { isOptimizableFlyerHost } from "@/lib/events/flyer-hosts";

type EventFlyerImageProps = {
  src: string;
  alt: string;
  fill?: boolean;
  sizes?: string;
  className?: string;
  priority?: boolean;
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
  sizes,
  className,
  priority,
  onError,
}: EventFlyerImageProps) {
  if (isOptimizableFlyerHost(src)) {
    return (
      <Image
        src={src}
        alt={alt}
        fill={fill}
        sizes={sizes}
        className={className}
        priority={priority}
        onError={onError}
      />
    );
  }

  const imgClassName = fill
    ? `absolute inset-0 h-full w-full ${className ?? ""}`.trim()
    : className;

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      className={imgClassName}
      loading={priority ? "eager" : "lazy"}
      onError={onError}
    />
  );
}
