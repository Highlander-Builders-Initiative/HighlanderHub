import { Masthead } from "@/components/Masthead";
import { Marquee } from "@/components/Marquee";
import { EventsBrowser } from "@/components/EventsBrowser";
import { Footer } from "@/components/Footer";
import { getEvents } from "@/lib/events";

export default async function HomePage() {
  const events = await getEvents();

  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />
      <Marquee />

      {/* Hero */}
      <section className="mx-auto max-w-7xl px-6 pt-16 pb-12 md:pt-24 md:pb-16">
        <div className="max-w-3xl">
          <span className="chip mb-5">
            <span className="h-1.5 w-1.5 rounded-full bg-highlander" />
            UC Riverside · Riverside, CA
          </span>
          <h1 className="font-display text-4xl md:text-6xl font-bold tracking-tight leading-[1.05] text-ink">
            Everything happening at UCR,{" "}
            <span className="text-highlander">in one place.</span>
          </h1>
          <p className="mt-5 text-lg text-muted max-w-2xl">
            Club meetings, mixers, mic nights, career fairs, and the occasional
            free-taco sighting — pulled from Instagram, Highlander Link, the UCR
            events calendar, and club websites.
          </p>
          <div className="mt-7 flex flex-wrap items-center gap-3">
            <a
              href="#events"
              className="inline-flex items-center gap-2 rounded-full bg-ink text-white px-5 py-2.5 text-sm font-medium hover:bg-highlander transition-colors"
            >
              Browse events <span aria-hidden>→</span>
            </a>
            <span className="text-xs text-muted">
              Showing placeholder data — scrapers not wired up yet.
            </span>
          </div>
        </div>
      </section>

      <EventsBrowser events={events} />

      <Footer />
    </main>
  );
}
