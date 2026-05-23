import Image from "next/image";
import Link from "next/link";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { FlyerMarquee } from "@/components/home/FlyerMarquee";
import { HeroHighlightCopy } from "@/components/home/hero-highlights";
import { HbiLink } from "@/components/analytics/HbiLink";
import { getEvents, getEventsSummary } from "@/lib/events";
import {
  formatPacificDayKey,
  formatUpcomingWeekLabel,
  pacificTodayKey,
} from "@/lib/dates";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  // The count is a nice-to-have; never let it fail the page if events loaded.
  const [events, summary] = await Promise.all([
    getEvents({ limit: 24 }),
    getEventsSummary().catch(() => null),
  ]);

  const dateLabel = formatPacificDayKey(pacificTodayKey());
  const weekLabel = formatUpcomingWeekLabel(
    summary?.upcomingThisWeek ?? null
  );

  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />

      {/* Hero: an editorial masthead over the living bulletin wall. */}
      <section className="relative overflow-hidden border-b border-ink/10">
        <div className="mx-auto max-w-7xl px-4 pt-11 pb-10 sm:px-6 md:pt-16 md:pb-12">
          {/* Dateline: a campus-paper colophon. */}
          <div
            className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 animate-fade-up"
            style={{ animationDelay: "0ms" }}
          >
            <p className="font-mono text-[12px] tracking-[0.04em] text-muted">
              {dateLabel}
              {weekLabel ? ` · ${weekLabel}` : ""}
            </p>

            <HbiLink
              href="https://www.instagram.com/hbi.ucr"
              location="hero"
              channel="instagram"
              className="interactive-focus group inline-flex items-center gap-2"
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
                Edited daily by{" "}
                <span className="font-medium text-ink">
                  Highlander Builders Initiative
                </span>
              </span>
            </HbiLink>
          </div>

          <h1
            className="mt-8 max-w-[15ch] font-display text-[44px] font-semibold leading-[1.03] tracking-[-0.035em] text-ink animate-fade-up sm:text-[56px] md:mt-10 md:text-[64px] lg:text-[72px]"
            style={{ animationDelay: "80ms" }}
          >
            Every UCR event,
            <span className="block text-muted">one page.</span>
          </h1>

          <p
            className="mt-7 max-w-md text-base leading-relaxed text-ink/75 animate-fade-up md:mt-9 md:text-lg"
            style={{ animationDelay: "180ms" }}
          >
            <HeroHighlightCopy />
          </p>

          <div
            className="mt-6 animate-fade-up md:mt-8"
            style={{ animationDelay: "260ms" }}
          >
            <Link
              href="/events"
              className="interactive-focus group inline-flex items-baseline gap-2 text-base font-medium text-ink"
            >
              <span className="underline underline-offset-[6px] decoration-ink/30 transition-colors duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:decoration-ink">
                Browse events
              </span>
              <svg
                aria-hidden
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-3.5 w-3.5 translate-y-px transition-transform duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:translate-x-0.5"
              >
                <path d="M3 8h10M9 4l4 4-4 4" />
              </svg>
            </Link>
          </div>
        </div>

        <div className="hairline" />

        {/* The wall: a full-bleed, self-scrolling strip of real flyers. */}
        <div
          className="pt-7 pb-12 animate-fade-up md:pt-9 md:pb-16"
          style={{ animationDelay: "300ms" }}
        >
          <p className="mx-auto mb-4 max-w-7xl px-4 text-[13px] text-muted sm:px-6">
            Now on the wall
          </p>
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
          <p className="text-[18px] leading-[1.5] text-ink sm:text-[20px] md:col-span-8 md:col-start-5 md:text-[22px]">
            We pull listings from where clubs already post: Instagram,
            events.ucr.edu, and HighlanderLink. One page instead of forty
            accounts to follow.
          </p>
        </div>
      </section>

      <Footer />
    </main>
  );
}
