"use client";

import type { ReactNode } from "react";
import { track } from "@/lib/analytics";

export function HbiLink({
  href,
  location,
  channel,
  className,
  ariaLabel,
  children,
}: {
  href: string;
  location: "hero" | "footer_social";
  channel: string;
  className?: string;
  ariaLabel?: string;
  children: ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={ariaLabel}
      className={className}
      onClick={() => track("hbi_cta_click", { location, channel })}
    >
      {children}
    </a>
  );
}
