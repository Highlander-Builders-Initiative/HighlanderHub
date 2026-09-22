"use client";

import { useState } from "react";
import { clubAvatarSrc, clubInitials } from "@/lib/club-avatars";

type ClubAvatarProps = {
  handle?: string | null;
  /** Display name; its initials stand in when the club has no picture. */
  name: string;
  /** Diameter in CSS pixels. Pictures are 128px, sharp up to 64px at 2x. */
  size?: number;
  className?: string;
};

/**
 * Circular club profile picture, falling back to a monogram. Decorative: it
 * always sits next to the club's name, so it is hidden from assistive tech.
 */
export function ClubAvatar({ handle, name, size = 32, className = "" }: ClubAvatarProps) {
  const src = clubAvatarSrc(handle);
  const [brokenSrc, setBrokenSrc] = useState<string>();
  const shape = `inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full ring-1 ring-ink/10 ${className}`;

  if (src && brokenSrc !== src) {
    return (
      // Pre-sized static file: the image optimizer would only add a hop.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt=""
        aria-hidden
        width={size}
        height={size}
        loading="lazy"
        decoding="async"
        draggable={false}
        onError={() => setBrokenSrc(src)}
        className={`${shape} bg-canvas object-cover`}
        style={{ width: size, height: size }}
      />
    );
  }

  return (
    <span
      aria-hidden
      className={`${shape} select-none bg-surface font-semibold text-ink`}
      style={{ width: size, height: size, fontSize: Math.max(9, Math.round(size * 0.34)) }}
    >
      {clubInitials(name || handle || "")}
    </span>
  );
}
