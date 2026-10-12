import type { CSSProperties } from "react";
import { FaApple } from "react-icons/fa";
import { FcGoogle } from "react-icons/fc";
import { calendarHref, icsHref } from "@/lib/events/actions";
import { TrackedAnchor } from "@/components/events/TrackedAnchor";
import type { CampusEvent } from "@/types/event";

type CalendarSurface = "desktop" | "mobile";

// The menu is a native popover (`.calendar-popover` in globals.css): a tap
// outside or Escape closes it, and it opens in the top layer, so the event
// overlay's scroll panel never clips it. Where it sits is set there too.
const POPOVER_CLASS =
  "calendar-popover w-44 overflow-clip rounded-lg border border-ink/15 bg-canvas p-0 text-ink shadow-menu";

const TRIGGER_CLASS: Record<CalendarSurface, string> = {
  desktop:
    "calendar-trigger interactive-focus press text-sm font-medium text-ink underline-offset-4 hover:underline",
  mobile:
    "calendar-trigger interactive-focus press inline-flex min-h-12 min-w-12 items-center justify-center rounded-lg bg-ink/[0.06] text-ink hover:bg-ink/10",
};

const CHOICE_CLASS =
  "interactive-focus flex min-h-11 items-center gap-2.5 px-4 text-sm font-medium text-ink transition-colors hover:bg-surface active:bg-ink/[0.06]";

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
        className={CHOICE_CLASS}
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
        className={CHOICE_CLASS}
      >
        <FcGoogle aria-hidden className="h-4 w-4 shrink-0" />
        <span>Google Calendar</span>
      </TrackedAnchor>
    </>
  );
}

// The same calendar as the When row's (EventDetailView), so the phone screen
// shows one calendar glyph, not two.
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
      <rect x="3.5" y="5" width="17" height="15.5" rx="2.5" />
      <path d="M16 3v4M8 3v4M3.5 10h17" />
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
  // The desktop row and the phone bar each render a menu, so the popover id
  // and the anchor name carry the surface as well as the event.
  const key = `${surface}-${event.id.replace(/[^\w-]/g, "_")}`;
  const popoverId = `calendar-menu-${key}`;

  return (
    <div
      className="shrink-0"
      style={{ "--calendar-anchor": `--calendar-${key}` } as CSSProperties}
    >
      <button
        type="button"
        popoverTarget={popoverId}
        aria-label={`${calendarLabel}: choose calendar app`}
        className={TRIGGER_CLASS[surface]}
      >
        {surface === "mobile" ? <CalendarIcon /> : calendarLabel}
      </button>
      <div id={popoverId} popover="auto" data-surface={surface} className={POPOVER_CLASS}>
        <CalendarChoiceLinks event={event} surface={surface} />
      </div>
    </div>
  );
}
