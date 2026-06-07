import { FaApple } from "react-icons/fa";
import { FcGoogle } from "react-icons/fc";
import { calendarHref, icsHref } from "@/lib/events/actions";
import { TrackedAnchor } from "@/components/events/TrackedAnchor";
import type { CampusEvent } from "@/types/event";

type CalendarSurface = "desktop" | "mobile";

const SURFACE_STYLES: Record<
  CalendarSurface,
  { details: string; summary: string; popover: string }
> = {
  desktop: {
    details: "relative",
    summary:
      "interactive-focus cursor-pointer list-none text-sm font-medium text-ink underline-offset-4 hover:underline [&::-webkit-details-marker]:hidden",
    popover:
      "absolute left-0 top-[calc(100%+0.5rem)] z-10 w-44 overflow-hidden rounded-lg border border-ink/15 bg-canvas shadow-[0_18px_44px_rgba(15,17,21,0.12)]",
  },
  mobile: {
    details: "relative shrink-0",
    summary:
      "interactive-focus inline-flex min-h-12 min-w-12 cursor-pointer list-none items-center justify-center rounded-lg border border-ink/15 text-ink [&::-webkit-details-marker]:hidden",
    popover:
      "absolute bottom-[calc(100%+0.5rem)] right-0 z-10 w-44 overflow-hidden rounded-lg border border-ink/15 bg-canvas shadow-[0_18px_44px_rgba(15,17,21,0.12)]",
  },
};

function CalendarChoiceLinks({
  event,
  surface,
}: {
  event: CampusEvent;
  surface: CalendarSurface;
}) {
  return (
    <>
      <TrackedAnchor
        event="calendar"
        method="ics"
        eventId={event.id}
        surface={surface}
        href={icsHref(event.id)}
        className="interactive-focus flex min-h-11 items-center gap-2.5 px-4 text-sm font-medium text-ink transition-colors hover:bg-surface"
      >
        <FaApple aria-hidden className="h-4 w-4 shrink-0" />
        <span>Apple Calendar</span>
      </TrackedAnchor>
      <div className="hairline" />
      <TrackedAnchor
        event="calendar"
        method="google"
        eventId={event.id}
        surface={surface}
        href={calendarHref(event)}
        className="interactive-focus flex min-h-11 items-center gap-2.5 px-4 text-sm font-medium text-ink transition-colors hover:bg-surface"
      >
        <FcGoogle aria-hidden className="h-4 w-4 shrink-0" />
        <span>Google Calendar</span>
      </TrackedAnchor>
    </>
  );
}

function CalendarIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
    >
      <rect x="3" y="4" width="18" height="18" rx="0" />
      <path d="M16 2v4M8 2v4M3 10h18" />
    </svg>
  );
}

export function EventCalendarMenu({
  event,
  calendarLabel,
  surface,
}: {
  event: CampusEvent;
  calendarLabel: string;
  surface: CalendarSurface;
}) {
  const { details, summary, popover } = SURFACE_STYLES[surface];

  return (
    <details className={details}>
      <summary
        role="button"
        aria-label={`${calendarLabel}: choose calendar app`}
        className={summary}
      >
        {surface === "mobile" ? <CalendarIcon /> : calendarLabel}
      </summary>
      <div className={popover}>
        <CalendarChoiceLinks event={event} surface={surface} />
      </div>
    </details>
  );
}
