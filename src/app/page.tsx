import Link from "next/link";
import { Masthead } from "@/components/Masthead";
import { Footer } from "@/components/Footer";
import { HeroMockup } from "@/components/HeroMockup";
import { Features, FinalCTA } from "@/components/LandingSections";
import { getEvents } from "@/lib/events";

export default async function HomePage() {
  const events = await getEvents();

  const now = Date.now();
  const inSevenDays = now + 7 * 24 * 60 * 60 * 1000;
  const upcomingThisWeek = events.filter((e) => {
    const t = new Date(e.startsAt).getTime();
    return t >= now && t <= inSevenDays;
  }).length;

  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />

      {/* Hero */}
      <section className="relative overflow-hidden border-b border-ink/10">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[480px]"
          style={{
            backgroundImage:
              "radial-gradient(60% 60% at 20% 0%, rgba(30,58,138,0.08), transparent 70%), radial-gradient(40% 50% at 90% 10%, rgba(245,180,0,0.10), transparent 70%)",
          }}
        />

        <div className="mx-auto grid max-w-7xl grid-cols-12 gap-x-8 gap-y-12 px-4 pt-14 pb-20 sm:px-6 md:pt-24 md:pb-28">
          <div className="col-span-12 md:col-span-6 md:pt-6">
            <div className="inline-flex items-center gap-2 border border-ink/15 bg-canvas px-3 py-1.5 text-xs text-ink">
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

            <h1 className="mt-6 font-display text-[44px] font-semibold leading-[0.95] tracking-[-0.035em] text-ink sm:text-[60px] md:text-[72px]">
              Every UCR event,
              <span className="block text-muted">One App.</span>
            </h1>

            <p className="mt-7 max-w-xl text-base leading-relaxed text-ink/75 md:text-lg">
              Meetings, mixers, mic nights, career fairs, and the occasional
              free taco run. All the campus stuff worth knowing about, filtered
              by what you actually care about.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                href="/events"
                className="interactive-focus inline-flex min-h-12 items-center gap-2 bg-ink px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-85"
              >
                Browse events
                <span aria-hidden>→</span>
              </Link>
              <a
                href="#features"
                className="interactive-focus inline-flex min-h-12 items-center px-3 py-3 text-sm font-medium text-ink underline underline-offset-4 decoration-ink/30 hover:decoration-ink"
              >
                See how it works
              </a>
            </div>

            <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted">
              <span className="flex items-center gap-2">
                <span className="text-ink">{events.length}</span> events indexed
              </span>
              <span className="hidden h-4 w-px bg-ink/15 sm:block" />
              <span className="flex items-center gap-2">
                <span className="text-ink">Updated daily</span>
              </span>
              <span className="hidden h-4 w-px bg-ink/15 sm:block" />
              <span className="flex items-center gap-2">
                <span className="text-ink">Free</span> for students
              </span>
            </div>
          </div>

          <div className="col-span-12 md:col-span-6">
            <HeroMockup />
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
