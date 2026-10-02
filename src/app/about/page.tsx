import type { Metadata } from "next";
import type { ReactNode } from "react";
import { FallbackImage } from "@/components/ui/FallbackImage";
import { FaInstagram } from "react-icons/fa";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { HbiLink } from "@/components/analytics/HbiLink";
import { EventsFeedLink } from "@/components/events/EventsFeedLink";
import { FlyerTrace } from "@/components/about/FlyerTrace";
import { HBI_ABOUT_URL, HBI_INSTAGRAM_URL } from "@/lib/hbi";
import { TRACKED_ACCOUNT_COUNT } from "@/lib/clubs";
import { getEvents } from "@/lib/events";
import { isDeadlineKind } from "@/lib/events/content-kind";
import { campusRunTimes } from "@/lib/run-schedule";
import {
  formatAllDay,
  pacificDayHeading,
  pacificDayKey,
  pacificTodayKey,
} from "@/lib/dates";
import type { CampusEvent } from "@/types/event";

export const metadata: Metadata = {
  title: "About",
  description:
    "Highlander Hub checks UCR club Instagram accounts three times a day, reads each new flyer, and lists the events on one page.",
};

// Rendered per request, like the home page: the example is a live event, read
// from the same cached feed the home page uses (see lib/events).
export const dynamic = "force-dynamic";

const HBI_DISCORD = "https://discord.com/invite/QYCQwTTvfS";
const ACCOUNT_COUNT = TRACKED_ACCOUNT_COUNT.toLocaleString("en-US");

const INLINE_LINK =
  "interactive-focus font-medium text-ink underline decoration-ink/25 underline-offset-4 transition-colors hover:decoration-ink";
/** Every section heading on the page, at the feed title's size. */
const SECTION_HEADING =
  "font-display text-[28px] font-semibold leading-[1.05] tracking-[-0.025em] text-ink sm:text-[34px]";

/** A flyer that shows every step of the read: a picture, a host, a place and
 *  a topic. Deadlines are skipped; their card reads as a due date rather
 *  than a plan. */
function showsEveryStep(event: CampusEvent) {
  return Boolean(
    event.imageUrl &&
      event.hostHandle &&
      event.location?.trim() &&
      event.category !== "other" &&
      !isDeadlineKind(event.contentKind)
  );
}

/**
 * The feed's first such flyer, preferring one that hasn't started and has a
 * clock time, so the card shows a time read off the flyer rather than "All
 * day through Oct 3" under a day that has already passed.
 */
function pickExample(events: readonly CampusEvent[]) {
  const now = Date.now();
  return (
    events.find(
      (event) =>
        showsEveryStep(event) &&
        Date.parse(event.startsAt) > now &&
        !formatAllDay(event.startsAt, event.endsAt)
    ) ?? events.find(showsEveryStep)
  );
}

function questions(): { q: string; a: ReactNode }[] {
  const runs = campusRunTimes();
  const dm = (
    <HbiLink
      href={HBI_INSTAGRAM_URL}
      location="about_page"
      channel="instagram"
      className={INLINE_LINK}
    >
      @hbi.ucr
    </HbiLink>
  );

  return [
    {
      q: "Where do the events come from?",
      a: (
        <>
          Instagram. We check {ACCOUNT_COUNT} accounts from HighlanderLink&rsquo;s
          club directory: student clubs, Greek life, cultural and faith groups,
          and campus offices. When one of them posts a flyer, it can end up here.
        </>
      ),
    },
    {
      q: "How up to date is it?",
      a: (
        <>
          Every account is checked three times a day, around{" "}
          {runs.slice(0, -1).join(", ")} and {runs.at(-1)}. A flyer posted in
          the morning is usually listed by that evening.
        </>
      ),
    },
    {
      q: "Does a person check every listing?",
      a: "No. Listings go up on their own, which is what keeps the week current. When one comes out wrong, we fix it by hand.",
    },
    {
      q: "A listing has the wrong date or room. What do I do?",
      a: <>DM {dm} on Instagram with a link to the event and we&rsquo;ll fix it.</>,
    },
    {
      q: "Isn’t this what HighlanderLink is for?",
      a: "In theory. In practice most clubs never post their events there, so its calendar stays thin. Clubs post flyers on Instagram, so that’s where we look.",
    },
    {
      q: "Is this run by UCR?",
      a: "No. Highlander Hub is an independent student project and isn’t affiliated with UC Riverside. It’s free to use, with no account needed.",
    },
  ];
}

export default async function AboutPage() {
  // The example is a nice-to-have; the page never fails without it.
  const events = await getEvents({ limit: 24 }).catch(() => []);
  const example = pickExample(events) ?? null;

  return (
    <main className="brand-type min-h-screen bg-canvas">
      <Masthead />

      {/* What it is, in one headline and one paragraph. */}
      <section>
        <div className="mx-auto grid max-w-7xl gap-6 px-4 pb-14 pt-12 sm:px-6 md:pb-20 md:pt-20 lg:grid-cols-12 lg:items-end lg:gap-10">
          <h1 className="max-w-[16ch] text-balance font-display text-[38px] font-semibold leading-[1.04] tracking-[-0.035em] text-ink sm:text-[48px] lg:col-span-7 lg:text-[56px]">
            We read club Instagram so you don&rsquo;t have to.
          </h1>
          <div className="lg:col-span-5">
            <p className="max-w-xl text-[17px] leading-[1.55] text-ink/80 sm:text-[19px]">
              UCR clubs announce events on Instagram, across {ACCOUNT_COUNT}{" "}
              accounts, where a flyer scrolls out of sight in a day. Highlander
              Hub checks all of them, reads each new flyer, and lists the events
              by day on one page.
            </p>
            <EventsFeedLink
              href="/events"
              className="interactive-focus group mt-7 inline-flex min-h-12 items-center gap-2 rounded-lg bg-ink px-6 py-3 text-sm font-medium text-canvas transition-opacity hover:opacity-85"
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
      </section>

      <FlyerTrace
        event={example}
        dayHeading={
          example
            ? pacificDayHeading(pacificDayKey(example.startsAt), pacificTodayKey())
            : null
        }
        headingClassName={SECTION_HEADING}
      />

      {/* Questions, answered in the open: they are short, and the answers
          are the point of the page. */}
      <section aria-labelledby="faq-heading">
        <div id="faq" className="mx-auto max-w-7xl px-4 pt-16 sm:px-6 md:pt-24">
          <h2 id="faq-heading" className={SECTION_HEADING}>
            Questions
          </h2>
          <dl className="mt-8 border-t border-ink/10 md:mt-10">
            {questions().map(({ q, a }) => (
              <div
                key={q}
                className="grid gap-2 border-b border-ink/10 py-5 md:py-6 lg:grid-cols-12 lg:gap-10"
              >
                <dt className="text-[17px] font-semibold leading-snug tracking-[-0.01em] text-ink lg:col-span-5">
                  {q}
                </dt>
                <dd className="max-w-[60ch] text-[16px] leading-relaxed text-ink/75 lg:col-span-7">
                  {a}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* Who it's for beyond students, and who made it. The questions' last
          hairline is the divider above. */}
      <section>
        <div className="mx-auto grid max-w-7xl gap-12 px-4 pb-16 pt-14 sm:px-6 md:grid-cols-2 md:gap-10 md:pb-24 md:pt-16">
          <div>
            <h2 id="clubs-heading" className={SECTION_HEADING}>
              Run a club?
            </h2>
            <p className="mt-4 max-w-md text-[16px] leading-relaxed text-ink/75">
              Keep posting on Instagram. If your account is one of the{" "}
              {ACCOUNT_COUNT} we check, your flyers show up here on their own.
              Not on the list yet? Send us your handle and you&rsquo;ll be in
              the next run.
            </p>
            <HbiLink
              href={HBI_INSTAGRAM_URL}
              location="about_page"
              channel="instagram"
              className="interactive-focus mt-6 inline-flex min-h-12 items-center gap-2 rounded-lg border border-ink/15 bg-canvas px-5 py-3 text-sm font-medium text-ink transition-colors hover:border-ink"
            >
              <FaInstagram aria-hidden className="h-4 w-4" />
              DM @hbi.ucr
            </HbiLink>
          </div>

          <div>
            <h2 id="hbi-heading" className={SECTION_HEADING}>
              Built by HBI
            </h2>
            <div className="mt-4 flex max-w-md gap-4">
              <FallbackImage
                src="/logo_icon.png"
                alt=""
                width={40}
                height={40}
                className="mt-1 h-10 w-10 shrink-0"
              />
              <p className="text-[16px] leading-relaxed text-ink/75">
                <HbiLink
                  href={HBI_ABOUT_URL}
                  location="about_page"
                  channel="website"
                  className={INLINE_LINK}
                >
                  Highlander Builders Initiative
                </HbiLink>{" "}
                is a selective student organization at UC Riverside where engineers
                and creatives build real-world projects together. Highlander Hub is one of
                them.
              </p>
            </div>
            <p className="mt-6 pl-14 text-[16px] text-ink/75">
              Want to build the next one?{" "}
              <HbiLink
                href={HBI_DISCORD}
                location="about_page"
                channel="discord"
                className={INLINE_LINK}
              >
                Join the Discord
              </HbiLink>
            </p>
          </div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
