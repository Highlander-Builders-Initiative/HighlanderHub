import type { ReactNode } from "react";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";

export function LegalDocumentLayout({
  kicker,
  title,
  revisedDate,
  children,
}: {
  kicker: string;
  title: string;
  revisedDate: string;
  children: ReactNode;
}) {
  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />

      <article className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16 md:py-20">
        <header className="border-b border-ink/10 pb-6">
          <p className="text-xs font-mono tracking-wider text-muted uppercase">
            {kicker}
          </p>
          <h1 className="mt-2 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            {title}
          </h1>
          <p className="mt-2 text-xs text-muted font-mono">
            LAST REVISED: {revisedDate}
          </p>
        </header>

        {children}
      </article>

      <Footer />
    </main>
  );
}
