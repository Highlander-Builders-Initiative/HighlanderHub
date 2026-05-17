import Image from "next/image";
import Link from "next/link";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { Features, FinalCTA } from "@/components/home/LandingSections";
import { FlyerMosaic } from "@/components/home/FlyerMosaic";
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
        <div className="mx-auto grid max-w-7xl grid-cols-12 gap-x-8 gap-y-12 px-4 pt-14 pb-20 sm:px-6 md:pt-24 md:pb-28">
          <div className="col-span-12 md:col-span-6 md:pt-6">
            <div
              className="inline-flex items-center gap-2 border border-ink/15 bg-canvas px-3 py-1.5 text-xs text-ink animate-fade-up"
              style={{ animationDelay: "0ms" }}
            >
              <span className="h-2 w-2 rounded-full bg-leaf" aria-hidden />
              <span>
                <span className="font-medium">{upcomingThisWeek}</span>
                <span className="text-muted"> events this week</span>
              </span>
            </div>

            <h1
              className="mt-6 font-display text-[36px] font-semibold leading-[1] tracking-[-0.035em] text-ink break-words sm:text-[60px] md:text-[72px] animate-fade-up"
              style={{ animationDelay: "80ms" }}
            >
              Every UCR event,
              <span className="block text-muted">one app.</span>
            </h1>

            <p
              className="mt-7 max-w-xl text-base leading-relaxed text-ink/75 md:text-lg animate-fade-up"
              style={{ animationDelay: "180ms" }}
            >
              Club meetings, mixers, career fairs, free food drops — everything
              happening on campus, in one place you can actually scan.
            </p>

            <div
              className="mt-8 animate-fade-up"
              style={{ animationDelay: "260ms" }}
            >
              <Link
                href="/events"
                className="interactive-focus inline-flex min-h-12 items-center bg-ink px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-85"
              >
                Browse events
              </Link>
            </div>

            <div
              className="mt-12 border-t border-ink/10 pt-6 animate-fade-up"
              style={{ animationDelay: "360ms" }}
            >
              <a
                href="https://www.instagram.com/hbi.ucr"
                target="_blank"
                rel="noopener noreferrer"
                className="interactive-focus group inline-flex items-center gap-3"
              >
                <Image
                  src="/logo_icon.png"
                  alt=""
                  width={40}
                  height={40}
                  aria-hidden
                  className="h-10 w-10 shrink-0 transition-transform group-hover:-rotate-3"
                />

                <span className="flex flex-col">
                  <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
                    Brought to you by
                  </span>
                  <span className="font-display text-[15px] font-semibold tracking-[-0.01em] text-ink transition-colors group-hover:text-highlander">
                    Highlander Builders Initiative
                  </span>
                </span>
              </a>
            </div>
          </div>

          <div className="col-span-12 md:col-span-6">
            <FlyerMosaic events={events} />
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
