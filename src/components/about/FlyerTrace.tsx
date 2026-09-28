import type { ReactNode } from "react";
import type { CampusEvent } from "@/types/event";
import { EVENT_CATEGORY_LABELS } from "@/types/event";
import { EventCard } from "@/components/events/EventCard";
import { EventsFeedLink } from "@/components/events/EventsFeedLink";
import { eventHosts } from "@/components/events/HostAvatars";
import { PostedFlyer } from "@/components/about/PostedFlyer";
import { eventFlyerAlt } from "@/lib/events/a11y";
import { hostNamesByline } from "@/lib/events/host-byline";
import { CATEGORY_PILL, FREE_FOOD_PILL } from "@/lib/category-colors";
import { formatDay, formatTimeRange } from "@/lib/dates";

const PILL = "inline-flex rounded-full px-2.5 py-0.5 text-[13px] font-medium";
const INLINE_LINK =
  "interactive-focus font-medium text-ink underline decoration-ink/25 underline-offset-4 transition-colors hover:decoration-ink";
/** Product data (the read-out, the card) reads in the feed's UI face, not
 *  the page's Bricolage. */
const UI_FACE = "font-body [--font-body:var(--font-ui)]";

type Step = {
  title: string;
  body: string;
  visual: ReactNode;
};

/**
 * How a listing gets made, told with one real flyer from this week: the post
 * as the club shared it, what was read off it, and the card it became. With
 * no example the steps still read, just without their pictures.
 */
export function FlyerTrace({
  event,
  dayHeading,
  headingClassName,
}: {
  event: CampusEvent | null;
  /** The feed's heading for the example's day, worked out on the server. */
  dayHeading: { label: string; weekday: string } | null;
  /** The page's section heading style, so every h2 on it matches. */
  headingClassName: string;
}) {
  const host = event ? eventHosts(event)[0] : undefined;
  const handle = host?.hostHandle?.replace(/^@/, "") || undefined;

  const steps: Step[] = [
    {
      title: "Posted",
      body: "A club shares a flyer on its own Instagram, the way it already does.",
      visual:
        event?.imageUrl && host ? (
          <PostedFlyer
            src={event.imageUrl}
            alt={eventFlyerAlt(event)}
            host={host.host || `@${handle}`}
            handle={handle}
            sourceUrl={event.sourceUrl ?? undefined}
          />
        ) : null,
    },
    {
      title: "Read",
      body: "Hub reads the caption and every slide, fine print included. Posts that aren’t events are skipped.",
      visual: event ? <Readout event={event} /> : null,
    },
    {
      title: "Listed",
      body: "It goes on the feed under its day, merged with any repeats and tagged by what you’d be doing.",
      visual:
        event && dayHeading ? (
          <div className={`max-w-xl ${UI_FACE}`}>
            <p className="mb-3 flex items-baseline gap-1.5 text-lg font-semibold tracking-[-0.01em] text-ink">
              {dayHeading.label}
              <span className="font-medium text-faint">{dayHeading.weekday}</span>
            </p>
            <EventCard event={event} />
            <EventsFeedLink
              href="/events"
              className={`${INLINE_LINK} mt-2 inline-flex min-h-11 items-center text-[14px]`}
            >
              See the rest of this week
            </EventsFeedLink>
          </div>
        ) : null,
    },
  ];

  return (
    <section
      id="how"
      aria-labelledby="how-heading"
      className="scroll-mt-14 border-y border-ink/10 bg-surface"
    >
      <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 md:py-20">
        <h2 id="how-heading" className={headingClassName}>
          How a flyer becomes a listing
        </h2>
        <p className="mt-3 max-w-xl text-[16px] leading-relaxed text-muted sm:text-[17px]">
          {event
            ? "One from this week, start to finish. Nobody typed any of it in."
            : "Every listing gets here the same way. Nobody types any of it in."}
        </p>

        {/* From lg the three steps sit side by side; subgrid lines their
            pictures up under captions of different lengths. */}
        <ol className="mt-10 grid gap-12 md:mt-12 lg:grid-cols-[16rem_minmax(0,4fr)_minmax(0,5fr)] lg:grid-rows-[auto_auto] lg:gap-x-12 lg:gap-y-6">
          {steps.map((step, i) => (
            <li
              key={step.title}
              className="grid content-start gap-5 lg:row-span-2 lg:grid-rows-subgrid"
            >
              <div>
                <h3 className="flex items-baseline gap-2.5 font-display text-[20px] font-semibold tracking-[-0.02em] text-ink">
                  <span className="text-[15px] font-medium tabular-nums text-muted">
                    {i + 1}
                  </span>
                  {step.title}
                </h3>
                <p className="mt-1.5 max-w-sm text-[15px] leading-relaxed text-muted">
                  {step.body}
                </p>
              </div>
              {step.visual ? <div className="min-w-0">{step.visual}</div> : null}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/** What was read off the flyer, one field per line. */
function Readout({ event }: { event: CampusEvent }) {
  const location = event.location?.trim();
  const rows: { label: string; value: ReactNode }[] = [
    { label: "What", value: <span className="font-medium">{event.title}</span> },
    {
      label: "When",
      value: (
        <>
          {formatDay(event.startsAt)}
          <span className="block text-muted">
            {formatTimeRange(event.startsAt, event.endsAt)}
          </span>
        </>
      ),
    },
    ...(location ? [{ label: "Where", value: location }] : []),
    { label: "Hosted by", value: hostNamesByline(eventHosts(event)) },
    ...(event.category !== "other"
      ? [
          {
            label: "Topic",
            value: (
              <span
                className={`${PILL} ${CATEGORY_PILL[event.category].highlight} ${CATEGORY_PILL[event.category].text}`}
              >
                {EVENT_CATEGORY_LABELS[event.category]}
              </span>
            ),
          },
        ]
      : []),
    {
      label: "Free food",
      value: event.hasFreeFood ? (
        <span className={`${PILL} ${FREE_FOOD_PILL.highlight} ${FREE_FOOD_PILL.text}`}>
          Yes
        </span>
      ) : (
        <span className="text-muted">Not mentioned</span>
      ),
    },
    {
      label: "RSVP",
      value: event.rsvpRequired ? "Required" : <span className="text-muted">Not mentioned</span>,
    },
  ];

  return (
    <dl
      className={`max-w-md divide-y divide-ink/[0.07] rounded-[20px] bg-canvas text-[15px] leading-snug ring-1 ring-ink/10 ${UI_FACE}`}
    >
      {rows.map((row) => (
        <div key={row.label} className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-3 px-4 py-2.5">
          <dt className="pt-px text-[13px] text-muted">{row.label}</dt>
          <dd className="min-w-0 break-words text-ink">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}
