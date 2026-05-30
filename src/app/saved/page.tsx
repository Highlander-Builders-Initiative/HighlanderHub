import type { Metadata } from "next";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { SavedEventsClient } from "@/components/events/SavedEventsClient";

export const metadata: Metadata = {
  title: "Saved · Highlander Hub",
  description: "Events you've saved on Highlander Hub, kept on this device.",
  robots: { index: false },
};

export default function SavedPage() {
  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <header className="mb-8">
          <h1 className="font-display text-[34px] font-semibold leading-[1.05] tracking-[-0.025em] text-ink sm:text-[44px]">
            Saved
          </h1>
          <p className="mt-3 text-muted">
            Events you&rsquo;ve saved, kept on this device. No account needed.
          </p>
        </header>
        <SavedEventsClient />
      </div>
      <Footer />
    </main>
  );
}
