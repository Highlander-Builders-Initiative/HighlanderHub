"use client";

import type { ReactNode } from "react";
import { track } from "@/lib/analytics";

type Surface = "desktop" | "mobile";

type Props = {
  href: string;
  eventId: string;
  surface: Surface;
  className?: string;
  ariaLabel?: string;
  children: ReactNode;
} & (
  | { event: "primary"; ctaKind: "rsvp" | "view_source" }
  | { event: "calendar" }
);

export function TrackedAnchor(props: Props) {
  const handleClick = () => {
    if (props.event === "primary") {
      track("event_primary_cta", {
        id: props.eventId,
        kind: props.ctaKind,
        surface: props.surface,
      });
    } else {
      track("event_add_to_calendar", {
        id: props.eventId,
        surface: props.surface,
      });
    }
  };

  return (
    <a
      href={props.href}
      target="_blank"
      rel="noreferrer"
      className={props.className}
      aria-label={props.ariaLabel}
      onClick={handleClick}
    >
      {props.children}
    </a>
  );
}
