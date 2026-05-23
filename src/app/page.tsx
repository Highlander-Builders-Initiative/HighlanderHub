import Image from "next/image";
import Link from "next/link";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { FlyerMarquee } from "@/components/home/FlyerMarquee";
import { HbiLink } from "@/components/analytics/HbiLink";
import { getEvents, getEventsSummary } from "@/lib/events";
import { formatPacificDayKey, pacificTodayKey } from "@/lib/dates";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  // The count is a nice-to-have; never let it fail the page if events loaded.
  const [events, summary] = await Promise.all([
    getEvents({ limit: 24 }),
    getEventsSummary().catch(() => null),
  ]);

  const dateLabel = formatPacificDayKey(pacificTodayKey());
  const weekCount = summary?.upcomingThisWeek ?? null;
  const weekLabel =
    weekCount === null
      ? null
      : weekCount === 0
        ? "nothing posted yet this week"
        : weekCount === 1
          ? "1 event this week"
          : `${weekCount} events this week`;

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
            <p className="font-mono text-[11px] tracking-[0.04em] text-muted">
              {dateLabel}
              {weekLabel ? ` · ${weekLabel}` : ""}
            </p>

            <HbiLink
              href="https://www.instagram.com/hbi.ucr"
              location="hero"
              channel="instagram"
              ariaLabel="Built by Highlander Builders Initiative"
              className="interactive-focus group inline-flex items-center gap-2"
            >
              <Image
                src="/logo_icon.png"
                alt=""
                width={20}
                height={20}
                aria-hidden
                className="h-5 w-5 shrink-0 transition-transform group-hover:-rotate-6"
              />
              <span className="text-[13px] text-muted transition-colors group-hover:text-ink">
                Built by{" "}
                <span className="font-medium text-ink">
                  Highlander Builders Initiative
                </span>
              </span>
            </HbiLink>
          </div>

          <div className="mt-5 hairline" />

          <h1
            className="mt-8 max-w-[15ch] font-display text-[38px] font-semibold leading-[1.03] tracking-[-0.035em] text-ink animate-fade-up sm:text-[56px] md:mt-10 md:text-[64px] lg:text-[72px]"
            style={{ animationDelay: "80ms" }}
          >
            Every UCR event,
            <span className="block text-muted">
              one app.
            </span>
          </h1>

          <div
            className="mt-7 flex flex-col gap-6 animate-fade-up md:mt-9 md:flex-row md:items-end md:justify-between"
            style={{ animationDelay: "180ms" }}
          >
            <p className="max-w-md text-base leading-relaxed text-ink/75 md:text-lg">
              Club nights, free food, career fairs. Everything happening on
              campus, pulled into one place you can actually scan.
            </p>

            <div className="flex items-center gap-5">
              <Link
                href="/events"
                className="interactive-focus group inline-flex min-h-12 items-center gap-2 rounded-lg bg-ink px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-85"
              >
                Browse events
                <svg
                  aria-hidden
                  viewBox="0 0 20 20"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5"
                >
                  <path d="M4 10h12M11 5l5 5-5 5" />
                </svg>
              </Link>
              <Link
                href="/submit"
                className="interactive-focus inline-flex min-h-12 items-center text-sm font-medium text-ink underline decoration-ink/30 underline-offset-4 transition-colors hover:decoration-ink"
              >
                Submit an event
              </Link>
            </div>
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

      <Footer />
    </main>
  );
}
