import type { Metadata } from "next";
import { Masthead } from "@/components/Masthead";
import { EventsBrowser } from "@/components/EventsBrowser";
import { Footer } from "@/components/Footer";
import { getEvents } from "@/lib/events";

export const metadata: Metadata = {
  title: "Events · Highlander Hub",
  description:
    "Browse and filter campus and club events at UC Riverside and around the city.",
};

export default async function EventsPage() {
  const events = await getEvents();

  const now = Date.now();
  const inSevenDays = now + 7 * 24 * 60 * 60 * 1000;
  const upcomingThisWeek = events.filter((e) => {
    const t = new Date(e.startsAt).getTime();
    return t >= now && t <= inSevenDays;
  }).length;
  const freeFoodCount = events.filter(
    (e) => e.category === "free_food" || e.tags.includes("free food")
  ).length;

  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />

      {/* Page header */}
      <section className="border-b border-ink/10">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 pt-10 pb-8 sm:px-6 md:flex-row md:items-end md:justify-between md:pt-14">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 border border-ink/15 bg-canvas px-3 py-1.5 text-xs text-ink">
              <span className="relative inline-flex h-2 w-2" aria-hidden="true">
                <span className="absolute inline-flex h-full w-full rounded-full bg-leaf opacity-60 animate-ping" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-leaf" />
              </span>
              <span>
                <span className="font-medium">{upcomingThisWeek}</span>
                <span className="text-muted"> events this week</span>
              </span>
              <span className="text-ink/20">·</span>
              <span className="text-muted">Indexed daily</span>
            </div>
            <h1 className="font-display text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-ink md:text-5xl">
              Events
            </h1>
            <p className="mt-3 max-w-xl text-base text-ink/75">
              Filter by category, search across hosts and tags, or switch to
              calendar view to see your whole month.
            </p>
          </div>
          <dl className="grid grid-cols-3 gap-x-6 gap-y-1 md:text-right">
            <div>
              <dt className="text-xs text-muted">Indexed</dt>
              <dd className="font-display text-2xl font-semibold leading-none text-ink">
                {events.length}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">This week</dt>
              <dd className="font-display text-2xl font-semibold leading-none text-ink">
                {upcomingThisWeek}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Free food</dt>
              <dd className="font-display text-2xl font-semibold leading-none text-ink">
                {freeFoodCount}
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <EventsBrowser events={events} />

      <Footer />
    </main>
  );
}
