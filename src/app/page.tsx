import Image from "next/image";
import Link from "next/link";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { EventsFeedLink } from "@/components/events/EventsFeedLink";
import { FlyerMarquee } from "@/components/home/FlyerMarquee";
import { CampusSkyline } from "@/components/home/CampusSkyline";
import { HeroHighlightCopy } from "@/components/home/hero-highlights";
import { HbiLink } from "@/components/analytics/HbiLink";
import { HBI_ABOUT_URL, HBI_INSTAGRAM_URL } from "@/lib/hbi";
import { TRACKED_ACCOUNT_COUNT } from "@/lib/clubs";
import { getEvents, getEventsSummary } from "@/lib/events";
import { campusDaypart } from "@/lib/daylight";
import {
  formatPacificDayKey,
  formatUpcomingWeekLabel,
  pacificTodayKey,
} from "@/lib/dates";

// Rendered per request: the Supabase client is hardwired to `cache: "no-store"`
// (see lib/supabase.ts), which bars static prerendering. The expensive reads are
// served from the Data Cache instead (see lib/events), so a visit avoids the
// Supabase round-trips; admin mutations bust it via revalidateTag("events").
export const dynamic = "force-dynamic";

export default async function HomePage() {
  // The count is a nice-to-have; never let it fail the page if events loaded.
  const [events, summary] = await Promise.all([
    getEvents({ limit: 24 }),
    getEventsSummary().catch(() => null),
  ]);

  const dateLabel = formatPacificDayKey(pacificTodayKey());
  // Which skyline the hero shows: day, golden hour or night over campus.
  const daypart = campusDaypart();
  const weekLabel = formatUpcomingWeekLabel(
    summary?.upcomingThisWeek ?? null
  );
  // The wall is a preview; this is the way on to the full week. The count is
  // the Week filter's own, so the number matches the list it opens.
  const weekCount = summary?.upcomingThisWeek ?? 0;
  const seeAll =
    weekCount > 1
      ? { href: "/events?when=week", label: `See all ${weekCount} this week` }
      : { href: "/events", label: "See all events" };

  return (
    <main className="brand-type min-h-screen bg-canvas">
      <Masthead />

      {/* Hero: an editorial masthead over the living bulletin wall, with the
          campus skyline standing on the hairline that separates the two. */}
      <section className="relative overflow-hidden border-b border-ink/10">
        <div className="skyline-hero relative" data-daypart={daypart}>
          <CampusSkyline daypart={daypart} />
          <div className="skyline-copy relative mx-auto max-w-7xl px-4 pt-11 sm:px-6 md:pt-16">
            {/* Dateline: a campus-paper colophon. */}
            <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
              <p className="text-[12px] text-muted">
                {dateLabel}
                {weekLabel ? ` · ${weekLabel}` : ""}
              </p>

              <HbiLink
                href={HBI_ABOUT_URL}
                location="hero"
                channel="website"
                className="interactive-focus group inline-flex items-center gap-2 md:mr-8 lg:mr-16"
              >
                <Image
                  src="/logo_icon.png"
                  alt=""
                  width={20}
                  height={20}
                  aria-hidden
                  className="h-5 w-5 shrink-0 transition-transform"
                />
                <span className="text-[13px] text-muted transition-colors group-hover:text-ink">
                  Built by{" "}
                  <span className="font-medium text-ink">
                    Highlander Builders Initiative
                  </span>
                </span>
              </HbiLink>
            </div>

            <h1
              className="mt-8 max-w-[15ch] font-display text-[44px] font-semibold leading-[1.03] tracking-[-0.035em] text-ink sm:text-[56px] md:mt-10 md:text-[64px] lg:text-[72px]"
            >
              Every UCR event,
              <span className="block text-ink">one page.</span>
            </h1>

            <p
              className="mt-7 max-w-md text-base leading-relaxed text-ink/75 md:mt-9 md:text-lg"
            >
              <HeroHighlightCopy />
            </p>

            <div className="mt-6 md:mt-8">
              <EventsFeedLink
                href="/events"
                className="interactive-focus group inline-flex min-h-12 items-center gap-2 rounded-lg bg-ink px-6 py-3 text-sm font-medium text-canvas transition-opacity hover:opacity-85"
              >
                Browse events
                <svg
                  aria-hidden
                  viewBox="0 0 16 16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5"
                >
                  <path d="M3 8h10M9 4l4 4-4 4" />
                </svg>
              </EventsFeedLink>
          </div>
          </div>
        </div>

        <div className="hairline" />

        {/* The wall: a full-bleed, self-scrolling strip of real flyers. */}
        <div className="pt-4 pb-12 md:pt-6 md:pb-16">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
            <p className="text-[13px] text-muted">Now on the wall</p>
            <EventsFeedLink
              href={seeAll.href}
              className="interactive-focus inline-flex min-h-11 items-center text-[13px] font-medium text-ink underline decoration-ink/25 underline-offset-4 transition-colors hover:decoration-ink"
            >
              {seeAll.label}
            </EventsFeedLink>
          </div>
          <FlyerMarquee events={events} />
        </div>
      </section>

      {/* Note from the editors: a short, honest colophon that says where the
          listings come from. Sits between the bulletin wall and the footer so
          the page has one more edited beat before it closes. */}
      <section aria-labelledby="editors-note">
        <div className="mx-auto grid max-w-7xl gap-6 px-4 py-16 sm:px-6 md:grid-cols-12 md:gap-10 md:py-24">
          <p
            id="editors-note"
            className="text-[13px] text-muted md:col-span-3"
          >
            Note from the editors
          </p>
          <div className="md:col-span-8 md:col-start-5">
            <p className="text-[18px] leading-[1.5] text-ink sm:text-[20px] md:text-[22px]">
              We pull listings from club Instagram posts. One page instead of{" "}
              {TRACKED_ACCOUNT_COUNT.toLocaleString("en-US")} accounts to
              follow.
            </p>
            <p className="mt-5 text-[15px] leading-relaxed text-muted sm:text-base">
              Run a club? Keep posting on Instagram like you already do. If
              we&rsquo;re missing you, DM{" "}
              <HbiLink
                href={HBI_INSTAGRAM_URL}
                location="editors_note"
                channel="instagram"
                className="interactive-focus font-medium text-ink underline decoration-ink/25 underline-offset-4 transition-colors hover:decoration-ink"
              >
                @hbi.ucr
              </HbiLink>
              .
            </p>
          </div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
