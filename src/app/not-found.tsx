import Link from "next/link";
import { Footer } from "@/components/layout/Footer";
import { Masthead } from "@/components/layout/Masthead";

export default function NotFound() {
  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />

      <section className="border-b border-ink/10">
        <div className="mx-auto flex min-h-[62vh] max-w-3xl flex-col items-start justify-center px-4 py-16 sm:px-6 md:py-24">
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
            Not found
          </p>
          <h1 className="mt-3 max-w-2xl font-display text-[34px] font-semibold leading-[1.05] tracking-[-0.03em] text-ink sm:text-[48px]">
            This event is no longer on Highlander Hub.
          </h1>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-ink/75">
            It may have been removed, rescheduled, or replaced with a newer
            listing. Browse the current feed to find what is still coming up.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/events"
              className="interactive-focus inline-flex min-h-12 items-center justify-center rounded-lg bg-ink px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-85"
            >
              Browse events
            </Link>
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
