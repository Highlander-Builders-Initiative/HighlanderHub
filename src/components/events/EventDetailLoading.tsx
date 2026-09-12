"use client";

import { usePathname } from "next/navigation";
import { EventBackButton } from "@/components/events/EventBackButton";
import { SaveButton } from "@/components/events/SaveButton";
import {
  EVENT_DETAIL_ASIDE_CLASS,
  EVENT_DETAIL_CONTAINER_CLASS,
  EVENT_DETAIL_FLYER_FRAME_CLASS,
  EVENT_DETAIL_FLYER_GRID_CLASS,
  EVENT_DETAIL_MOBILE_BAR_CLASS,
  EVENT_DETAIL_TILE_CLASS,
  EventDetailView,
  LocationPinIcon,
} from "@/components/events/EventDetailView";
import { peekEventForDetail } from "@/lib/events/detail-handoff";

/**
 * Loading state for /events/[id].
 *
 * Opened from a list card: the card handed its event off, so the real page
 * renders immediately and the server response swaps in identical markup.
 *
 * Opened cold (shared link, refresh): a skeleton on the flyer layout. Anything
 * that does not depend on the event row renders for real — Back, section
 * labels, the Save toggle (it only needs the id from the URL). Bars are static,
 * no pulse, matching the /events skeleton.
 */

function eventIdFromPath(pathname: string | null): string | null {
  const segment = pathname?.split("/").filter(Boolean)[1];
  if (!segment) return null;
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

function Bar({ className }: { className: string }) {
  return <span aria-hidden className={`block rounded-full bg-ink/10 ${className}`} />;
}

/** A bar vertically centered in a box sized to one line of the real text. */
function LineBar({ line, bar }: { line: string; bar: string }) {
  return (
    <span aria-hidden className={`flex items-center ${line}`}>
      <Bar className={bar} />
    </span>
  );
}

function EventDetailSkeleton({ eventId }: { eventId: string | null }) {
  return (
    <>
      <p className="sr-only" role="status">
        Loading event
      </p>

      <div className={EVENT_DETAIL_CONTAINER_CLASS}>
        <EventBackButton />

        <article className="mt-7 md:mt-10">
          <header>
            {/* Category + flag pills: 12px text, py-0.5 */}
            <div className="flex flex-wrap items-center gap-2">
              <Bar className="h-[22px] w-20" />
              <Bar className="h-[22px] w-12" />
            </div>

            {/* Title: one line per 34px / 44px line box */}
            <div className="mt-5 max-w-3xl">
              <LineBar
                line="h-[36px] sm:h-[46px]"
                bar="h-[26px] w-full sm:h-[34px] sm:w-3/4"
              />
              <LineBar line="h-[36px] sm:hidden" bar="h-[26px] w-1/2" />
            </div>
          </header>

          <div className={EVENT_DETAIL_FLYER_GRID_CLASS}>
            <aside className={EVENT_DETAIL_ASIDE_CLASS}>
              <div className={EVENT_DETAIL_FLYER_FRAME_CLASS}>
                <div className="relative aspect-[4/5] w-full bg-ink/[0.04]" />
              </div>

              <dl className="space-y-4 text-[14px]">
                <div>
                  <dt className="text-[12px] text-muted">Hosted by</dt>
                  <dd className="mt-1">
                    <LineBar line="h-[21px]" bar="h-3.5 w-36" />
                  </dd>
                </div>
                <div className="hairline" />
                <div>
                  <dt className="text-[12px] text-muted">Source</dt>
                  <dd className="mt-1">
                    <LineBar line="h-[21px]" bar="h-3 w-20" />
                  </dd>
                </div>
              </dl>
            </aside>

            <div className="order-1 min-w-0 md:order-2">
              <section className="space-y-3">
                <div className="flex items-center gap-4">
                  <div className={`${EVENT_DETAIL_TILE_CLASS} flex-col gap-1.5`}>
                    <Bar className="h-2 w-6" />
                    <Bar className="h-4 w-6" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <LineBar line="h-[25px]" bar="h-4 w-44" />
                    <LineBar line="mt-0.5 h-[21px]" bar="h-3 w-52 max-w-full" />
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className={EVENT_DETAIL_TILE_CLASS}>
                    <LocationPinIcon />
                  </div>
                  <div className="min-w-0 flex-1">
                    <LineBar line="h-[22px]" bar="h-3.5 w-48 max-w-full" />
                  </div>
                </div>
              </section>

              <section className="mt-8 hidden rounded-xl border border-ink/15 bg-canvas p-5 md:block">
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                  <LineBar line="h-[19px]" bar="h-3 w-20" />
                  <LineBar line="h-[19px]" bar="h-3 w-24" />
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-3">
                  <span className="block h-12 w-[104px] rounded-lg bg-ink/10" />
                  <LineBar line="h-5" bar="h-3.5 w-28" />
                  {eventId ? (
                    <SaveButton eventId={eventId} surface="detail" variant="label" />
                  ) : (
                    <LineBar line="h-5" bar="h-3.5 w-12" />
                  )}
                  <LineBar line="h-5" bar="h-3.5 w-10" />
                </div>
              </section>

              <section className="mt-10">
                <div className="hairline" />
                <h2 className="mt-7 font-display text-[20px] font-semibold tracking-[-0.015em] text-ink">
                  About
                </h2>
                {/* 16px / leading-relaxed = 26px per line */}
                <div className="mt-4 max-w-prose">
                  {["w-full", "w-11/12", "w-full", "w-2/3"].map((width, i) => (
                    <LineBar key={i} line="h-[26px]" bar={`h-3.5 ${width}`} />
                  ))}
                </div>
              </section>
            </div>
          </div>
        </article>
      </div>

      <div className={EVENT_DETAIL_MOBILE_BAR_CLASS}>
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          <span aria-hidden className="block h-12 flex-1 rounded-lg bg-ink/10" />
          <span
            aria-hidden
            className="inline-flex min-h-12 min-w-12 items-center justify-center rounded-lg border border-ink/15"
          >
            <Bar className="h-4 w-4" />
          </span>
          {eventId && (
            <SaveButton eventId={eventId} surface="detail" variant="icon" />
          )}
          <span
            aria-hidden
            className="inline-flex min-h-12 min-w-12 items-center justify-center rounded-lg border border-ink/15"
          >
            <Bar className="h-4 w-4" />
          </span>
        </div>
      </div>
    </>
  );
}

export function EventDetailLoading() {
  const eventId = eventIdFromPath(usePathname());
  const handedOff = eventId ? peekEventForDetail(eventId) : null;

  if (handedOff) return <EventDetailView event={handedOff} />;
  return <EventDetailSkeleton eventId={eventId} />;
}
