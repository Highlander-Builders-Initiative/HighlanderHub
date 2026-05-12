import { Masthead } from "@/components/Masthead";
import { Marquee } from "@/components/Marquee";
import { EventsBrowser } from "@/components/EventsBrowser";
import { Footer } from "@/components/Footer";
import { getEvents } from "@/lib/events";

export default async function HomePage() {
  const events = await getEvents();

  return (
    <main className="min-h-screen">
      <Masthead />
      <Marquee text="Campus Bulletin · Updated Daily · Free Food Alerts · Club Nights · Career Fairs · Off-Campus" />

      {/* Lead section / hero */}
      <section className="mx-auto max-w-7xl px-6 py-12">
        <div className="grid gap-8 md:grid-cols-3">
          <div className="md:col-span-2">
            <p className="font-mono text-[11px] uppercase tracking-widest text-ink/60 mb-3">
              From the Editors
            </p>
            <p className="font-display italic text-4xl md:text-5xl leading-[1.05] tracking-tight">
              Every meeting, mixer, mic night, and mt. Rubidoux hike in one
              place — because the group chats are not enough.
            </p>
          </div>
          <aside className="col-rule pl-6 flex flex-col gap-3">
            <p className="font-mono text-[11px] uppercase tracking-widest text-ink/60">
              How this works
            </p>
            <p className="font-body text-base text-ink/80">
              Events are pulled from Instagram, Highlander Link, the UCR events
              calendar, and club websites. Filter by category, search for
              what&apos;s tonight, and don&apos;t miss the free tacos.
            </p>
            <p className="font-mono text-[10px] uppercase tracking-widest text-clay">
              ⚠ Showing placeholder data — scrapers not wired up yet
            </p>
          </aside>
        </div>
      </section>

      <EventsBrowser events={events} />

      <Footer />
    </main>
  );
}
