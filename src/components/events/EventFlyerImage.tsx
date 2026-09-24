"use client";

import Image from "next/image";
import { type CSSProperties, useState, useSyncExternalStore } from "react";
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

const subscribe = () => () => {};

// Flyers this session has shown, by source and rendered size (`sizes`, or the
// fixed width when there is none), which picks the optimized file. Showing one
// again finds it cached, so it skips the fade: a remount, like the overlay
// swapping its instant view for the server's, would otherwise blink.
const shownFlyers = new Set<string>();
// The feed's optimized thumbnail can paint immediately while a detail view
// downloads a larger variant, especially on high-density phone screens.
const loadedFlyers = new Map<string, string>();

/**
 * Whether this flyer fades in when it arrives, decided once at mount. Flyers
 * mounted in the browser (a client navigation, the next page of the feed,
 * the event overlay) stay hidden over their shimmering slot until loaded,
 * then fade in, so they never paint in strips. Flyers in the server's HTML
 * show as soon as they paint: hiding them until hydration would hold back
 * the page's largest image on JS.
 */
function useFadesIn(key: string) {
  const mountedInBrowser = useSyncExternalStore(
    subscribe,
    () => true,
    () => false
  );
  const [fadesIn] = useState(() => mountedInBrowser && !shownFlyers.has(key));
  return fadesIn;
}

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
  const shownKey = `${sizes ?? width ?? ""} ${src}`;
  const fadesIn = useFadesIn(shownKey);
  const [shownSrc, setShownSrc] = useState<string | null>(null);
  const previewSrc = useSyncExternalStore(
    subscribe,
    () => loadedFlyers.get(src) ?? null,
    () => null
  );
  const loading = fadesIn && shownSrc !== src;
  const hidden = loading && !previewSrc;
  const imageStyle: CSSProperties | undefined = loading && previewSrc
    ? {
        ...style,
        backgroundImage: `url(${JSON.stringify(previewSrc)})`,
        backgroundSize: "contain",
        backgroundPosition: "center",
        backgroundRepeat: "no-repeat",
      }
    : style;
  const fadeClassName = `transition-opacity duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]${
    hidden ? " opacity-0" : ""
  }`;
  const handleLoad = (img: HTMLImageElement) => {
    shownFlyers.add(shownKey);
    loadedFlyers.set(src, img.currentSrc || img.src);
    setShownSrc(src);
    onLoad?.(img);
  };

  if (isOptimizableFlyerHost(src)) {
    return (
      <Image
        src={src}
        alt={alt}
        fill={fill}
        width={fill ? undefined : width}
        height={fill ? undefined : height}
        sizes={sizes}
        className={`${className ?? ""} ${fadeClassName}`.trim()}
        style={imageStyle}
        priority={priority}
        onLoad={(event) => handleLoad(event.currentTarget)}
        onError={onError}
      />
    );
  }

  const imgClassName = `${fill ? "absolute inset-0 h-full w-full " : ""}${
    className ?? ""
  } ${fadeClassName}`.trim();

  // React re-attaches an inline ref on every render, so report each loaded
  // source once, as next/image does.
  const reportLoad = (img: HTMLImageElement) => {
    if (reportedSrc.get(img) === img.currentSrc) return;
    reportedSrc.set(img, img.currentSrc);
    handleLoad(img);
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
      style={imageStyle}
      loading={priority ? "eager" : "lazy"}
      decoding="async"
      onLoad={(event) => reportLoad(event.currentTarget)}
      onError={onError}
    />
  );
}

const reportedSrc = new WeakMap<HTMLImageElement, string>();
