import Link from "next/link";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { Features, FinalCTA } from "@/components/home/LandingSections";
import { EventCard } from "@/components/events/EventCard";
import { getEvents } from "@/lib/events";

export default async function HomePage() {
  const events = await getEvents();

  const now = Date.now();
  const inSevenDays = now + 7 * 24 * 60 * 60 * 1000;
  const upcomingThisWeek = events.filter((e) => {
    const t = new Date(e.startsAt).getTime();
    return t >= now && t <= inSevenDays;
  }).length;

  const nextFew = events.slice(0, 4);

  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />

      {/* Hero */}
      <section className="relative overflow-hidden border-b border-ink/10">
        <div className="mx-auto grid max-w-7xl grid-cols-12 gap-x-8 gap-y-12 px-4 pt-14 pb-20 sm:px-6 md:pt-24 md:pb-28">
          <div className="col-span-12 md:col-span-6 md:pt-6">
            <div className="inline-flex items-center gap-2 border border-ink/15 bg-canvas px-3 py-1.5 text-xs text-ink">
              <span className="h-2 w-2 rounded-full bg-leaf" aria-hidden />
              <span>
                <span className="font-medium">{upcomingThisWeek}</span>
                <span className="text-muted"> events this week</span>
              </span>
            </div>

            <h1 className="mt-6 font-display text-[36px] font-semibold leading-[1] tracking-[-0.035em] text-ink break-words sm:text-[60px] md:text-[72px]">
              Every UCR event,
              <span className="block text-muted">one app.</span>
            </h1>

            <p className="mt-7 max-w-xl text-base leading-relaxed text-ink/75 md:text-lg">
              Club meetings, mixers, career fairs, free food drops — everything
              happening on campus, in one place you can actually scan.
            </p>

            <div className="mt-8">
              <Link
                href="/events"
                className="interactive-focus inline-flex min-h-12 items-center bg-ink px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-85"
              >
                Browse events
              </Link>
            </div>
          </div>

          <div className="col-span-12 md:col-span-6">
            <div className="flex items-baseline justify-between border-b border-ink/10 pb-3">
              <h2 className="font-display text-base font-semibold tracking-[-0.02em] text-ink">
                Next up
              </h2>
              <Link
                href="/events"
                className="interactive-focus text-xs text-muted underline underline-offset-4 decoration-ink/20 transition-colors hover:text-ink hover:decoration-ink"
              >
                See all
              </Link>
            </div>
            {nextFew.length === 0 ? (
              <p className="mt-4 border border-dashed border-ink/15 bg-canvas px-4 py-6 text-sm text-muted">
                Nothing scheduled in the next few days. Check back soon.
              </p>
            ) : (
              <ul className="flex flex-col gap-3 pt-4">
                {nextFew.map((event) => (
                  <li key={event.id} className="min-w-0">
                    <EventCard event={event} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      <div id="features">
        <Features />
      </div>

      <FinalCTA />

      <Footer />
    </main>
  );
}
