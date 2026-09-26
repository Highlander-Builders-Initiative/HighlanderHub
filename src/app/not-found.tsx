import type { Metadata } from "next";
import Link from "next/link";
import { Footer } from "@/components/layout/Footer";
import { Masthead } from "@/components/layout/Masthead";
import { EventsFeedLink } from "@/components/events/EventsFeedLink";
import { SITE_NAME } from "@/lib/seo";

// Absolute: the root layout's title template skips its own not-found.
export const metadata: Metadata = {
  title: { absolute: `Page not found · ${SITE_NAME}` },
};

// Catches every unmatched URL. A missing /events/[id] has its own not-found
// sheet, so this copy stays general.
export default function NotFound() {
  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />

      <section className="border-b border-ink/10">
        <div className="mx-auto flex min-h-[62vh] max-w-3xl flex-col items-start justify-center px-4 py-16 sm:px-6 md:py-24">
          <p className="text-[13px] text-muted">Not found</p>
          <h1 className="mt-3 max-w-2xl font-display text-[34px] font-semibold leading-[1.05] tracking-[-0.03em] text-ink sm:text-[48px]">
            There&rsquo;s no page at this address.
          </h1>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-ink/75">
            The link may be mistyped or out of date. Everything on the site
            starts from the events feed.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <EventsFeedLink
              href="/events"
              className="interactive-focus inline-flex min-h-12 items-center justify-center rounded-lg bg-ink px-6 py-3 text-sm font-medium text-canvas transition-opacity hover:opacity-85"
            >
              Browse events
            </EventsFeedLink>
            <Link
              href="/"
              className="interactive-focus inline-flex min-h-12 items-center justify-center rounded-lg border border-ink/15 px-6 py-3 text-sm font-medium text-ink transition-colors hover:border-ink"
            >
              Go home
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
