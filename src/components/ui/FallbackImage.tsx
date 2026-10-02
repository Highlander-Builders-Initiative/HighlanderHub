"use client";

import Image, { type ImageProps } from "next/image";
import { useState } from "react";

/**
 * next/image that serves the original file when the optimizer refuses it
 * (Vercel answers 402 once the plan's transformations run out), so a quota
 * miss costs sharpness instead of leaving a broken image. Flyers get the same
 * retry inside EventFlyerImage.
 */
export function FallbackImage({ alt, ...props }: ImageProps) {
  const [optimizerFailed, setOptimizerFailed] = useState(false);
  return (
    <Image
      {...props}
      alt={alt}
      unoptimized={optimizerFailed || props.unoptimized}
      onError={() => setOptimizerFailed(true)}
    />
  );
}
