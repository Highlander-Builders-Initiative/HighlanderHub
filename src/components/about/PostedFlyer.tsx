"use client";

import { useState } from "react";
import { ClubAvatar } from "@/components/ui/ClubAvatar";
import { FlyerPoster } from "@/components/events/FlyerPoster";

const INLINE_LINK =
  "interactive-focus font-medium text-ink underline decoration-ink/25 underline-offset-4 transition-colors hover:decoration-ink";

/**
 * The example as its club posted it: who posted it, then the flyer, whole.
 * If the flyer won't load, the byline and the link stand alone rather than
 * above an empty frame.
 */
export function PostedFlyer({
  src,
  alt,
  host,
  handle,
  sourceUrl,
}: {
  src: string;
  alt: string;
  host: string;
  handle?: string;
  sourceUrl?: string;
}) {
  const [broken, setBroken] = useState(false);

  return (
    <div>
      <div className="flex items-center gap-2.5">
        <ClubAvatar handle={handle} name={host} size={32} />
        <p className="min-w-0 leading-tight">
          <span className="block truncate text-[14px] font-semibold text-ink">{host}</span>
          {handle ? (
            <span className="block truncate text-[13px] text-muted">@{handle}</span>
          ) : null}
        </p>
      </div>

      {broken ? null : (
        <div className="mt-3 flex [--flyer-anchor:left_top] [--flyer-max-h:20rem] [--flyer-max-w:16rem]">
          <FlyerPoster
            src={src}
            alt={alt}
            width={256}
            className="rounded-xl bg-ink/[0.05] ring-1 ring-ink/10"
            onError={() => setBroken(true)}
          />
        </div>
      )}

      {sourceUrl ? (
        <a
          href={sourceUrl}
          target="_blank"
          rel="noreferrer"
          className={`${INLINE_LINK} mt-2 inline-flex min-h-11 items-center text-[14px]`}
        >
          View the post
        </a>
      ) : null}
    </div>
  );
}
