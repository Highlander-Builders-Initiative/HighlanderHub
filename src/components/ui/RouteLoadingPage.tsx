import { Footer } from "@/components/layout/Footer";
import { Masthead } from "@/components/layout/Masthead";

function LoadingCards() {
  return (
    <div className="grid gap-3 md:grid-cols-3" aria-hidden="true">
      {Array.from({ length: 3 }).map((_, index) => (
        <div
          key={index}
          className="min-h-32 rounded-xl border border-ink/15 bg-canvas p-5"
        >
          <div className="h-2 w-14 skeleton rounded-full bg-ink/10" />
          <div className="mt-5 h-4 w-3/4 skeleton rounded-full bg-ink/10" />
          <div className="mt-3 h-3 w-full skeleton rounded-full bg-ink/10" />
          <div className="mt-2 h-3 w-2/3 skeleton rounded-full bg-ink/10" />
        </div>
      ))}
    </div>
  );
}

export function RouteLoadingPage() {
  return (
    <main className="min-h-screen bg-canvas" aria-busy="true">
      <Masthead />

      <section className="border-b border-ink/10">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 md:py-24">
          <p className="text-[13px] text-muted">About</p>
          <h1 className="mt-4 max-w-2xl font-display text-[34px] font-semibold leading-[1.05] tracking-[-0.03em] text-ink md:text-5xl">
            Loading Highlander Hub
          </h1>
          <p className="mt-3 max-w-xl text-base text-ink/70">
            Preparing the project details.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <LoadingCards />
      </section>

      <Footer />
    </main>
  );
}
