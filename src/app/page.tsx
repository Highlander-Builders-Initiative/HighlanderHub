import Image from "next/image";
import Link from "next/link";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { Features, FinalCTA } from "@/components/home/LandingSections";
import { FlyerMosaic } from "@/components/home/FlyerMosaic";
import { HbiLink } from "@/components/analytics/HbiLink";
import { getEvents } from "@/lib/events";

export default async function HomePage() {
  const events = await getEvents();

  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />

      {/* Hero */}
      <section className="relative overflow-hidden border-b border-ink/10">
        <div className="mx-auto grid max-w-7xl grid-cols-12 gap-x-8 gap-y-12 px-4 pt-14 pb-20 sm:px-6 md:pt-24 md:pb-28">
          <div className="col-span-12 md:col-span-6 md:pt-6">
            <h1
              className="font-display text-[36px] font-semibold leading-[1] tracking-[-0.035em] text-ink break-words sm:text-[60px] md:text-[72px] animate-fade-up"
              style={{ animationDelay: "0ms" }}
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
            </div>

            <div
              className="mt-12 border-t border-ink/10 pt-6 animate-fade-up"
              style={{ animationDelay: "360ms" }}
            >
              <HbiLink
                href="https://www.instagram.com/hbi.ucr"
                location="hero"
                channel="instagram"
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
              </HbiLink>
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
