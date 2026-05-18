import type { Metadata } from "next";
import SubmitForm from "@/components/forms/SubmitForm";

export const metadata: Metadata = {
  title: "Submit an event — Highlander Hub",
  description:
    "Submit a UC Riverside club, campus, or Riverside community event for review on Highlander Hub.",
};

export default function SubmitPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <header className="mb-10">
        <h1 className="font-serif text-5xl tracking-tight">Submit an event</h1>
        <p className="mt-3 text-stone-600">
          Got a club meeting, lecture, or anything happening at UCR? Drop the
          details below. We&apos;ll review and add it to the bulletin within a
          day.
        </p>
      </header>
      <SubmitForm />
    </main>
  );
}
