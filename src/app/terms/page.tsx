import type { Metadata } from "next";
import Link from "next/link";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { Reveal } from "@/components/ui/Reveal";

export const metadata: Metadata = {
  title: "Terms of Service · Highlander Hub",
  description: "Terms of Service and guidelines for using Highlander Hub, our event submission rules, and disclaimer information.",
};

const STATS_CARD = [
  { label: "Project Status", value: "Student-Led" },
  { label: "Liability & Warranty", value: "As-Is" },
  { label: "UCR Affiliation", value: "Independent" },
] as const;

const TERMS_SECTIONS = [
  {
    id: "acceptance",
    title: "1. Acceptance of Terms",
    body: (
      <div className="space-y-4">
        <p>
          By accessing or using Highlander Hub (the &ldquo;Service&rdquo;), developed and maintained by the{" "}
          <Link
            href="/about"
            className="font-medium text-ink underline decoration-ink/20 underline-offset-4 hover:decoration-ink"
          >
            Highlander Builders Initiative (HBI)
          </Link>
          , you agree to comply with and be bound by these Terms of Service.
        </p>
        <p>
          If you do not agree to these terms, please do not use the Service. We reserve the right to update or modify these Terms of Service at any time, and your continued use of Highlander Hub constitutes acceptance of those changes.
        </p>
      </div>
    ),
  },
  {
    id: "disclaimer",
    title: "2. Independent Status & Content Disclaimer",
    body: (
      <div className="space-y-4">
        <p>
          Highlander Hub is a student-built directory that aggregates campus events to help UC Riverside students discover activities.
        </p>
        <p className="font-semibold text-ink">
          We are NOT affiliated with, endorsed by, sponsored by, or in any way officially connected to the University of California, Riverside (UCR), or the Regents of the University of California.
        </p>
        <p>
          Because we aggregate data from public feeds and student submissions:
        </p>
        <ul className="list-disc pl-5 space-y-2 text-ink/80">
          <li>We do not guarantee the accuracy, completeness, timeliness, or reliability of any event details (such as dates, times, locations, or cancellations).</li>
          <li>Student organizations can reschedule or cancel events at any time. We encourage you to verify event details directly with the hosting organization prior to attending.</li>
        </ul>
      </div>
    ),
  },
  {
    id: "submissions",
    title: "3. Submission Rules & License",
    body: (
      <div className="space-y-4">
        <p>
          When you submit an event (including details, contact handles, and promotional flyers) via our submission portal:
        </p>
        <ul className="list-disc pl-5 space-y-2 text-ink/80">
          <li><strong>Ownership:</strong> You retain ownership of any original media (like a custom club logo or unique flyer artwork) you upload.</li>
          <li><strong>License:</strong> You grant us a worldwide, non-exclusive, royalty-free, perpetual, transferable license to host, display, resize, crop, and publish the event details and flyer images for the purpose of running the Service.</li>
          <li><strong>Representations:</strong> You warrant that you have all necessary rights, power, and authority to submit the event details and that your submission does not violate the intellectual property or privacy rights of any third party.</li>
        </ul>
        <p className="mt-4">
          We reserve the right to review, reject, edit, or remove any manual event submission at our sole discretion, without notice or liability, if we deem it inaccurate, inappropriate, spam, or a violation of campus community standards.
        </p>
      </div>
    ),
  },
  {
    id: "intellectual-property",
    title: "4. Intellectual Property & Fair Use",
    body: (
      <div className="space-y-4">
        <p>
          The Highlander Hub logo, platform interface design, search indexes, custom codebase, and branding belong exclusively to the Highlander Builders Initiative.
        </p>
        <p>
          Event flyers, promotional graphics, organization logos, and brand marks displayed in our feed are the property of their respective student organizations, UCR departments, or copyright owners. We crawl and display these materials for informational, commentary, and non-commercial educational purposes under the principles of **Fair Use** to assist the student body.
        </p>
      </div>
    ),
  },
  {
    id: "liability",
    title: "5. Limitation of Liability",
    body: (
      <div className="space-y-4">
        <p>
          THE SERVICE IS PROVIDED ON AN &ldquo;AS IS&rdquo; AND &ldquo;AS AVAILABLE&rdquo; BASIS. HIGHLANDER BUILDERS INITIATIVE DISCLAIMS ALL WARRANTIES, EXPRESS OR IMPLIED, INCLUDING IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
        </p>
        <p>
          IN NO EVENT SHALL HBI, ITS PROJECT MEMBERS, DEVELOPERS, OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES ARISING OUT OF YOUR USE OF THE SERVICE, ANY INACCURACIES IN EVENT DETAILS, OR YOUR PARTICIPATION IN EVENTS HOSTED BY THIRD-PARTY ORGANIZATIONS listed on our platform.
        </p>
      </div>
    ),
  },
  {
    id: "governing-law",
    title: "6. Moderation & Abuse",
    body: (
      <div className="space-y-4">
        <p>
          We do not tolerate spam, abusive submissions, or attempts to disrupt Highlander Hub systems. We reserve the right to restrict submission privileges, block certain domains or IP ranges, or disable automated aggregation for any student organization that violates community standards or attempts to exploit the platform.
        </p>
        <p>
          If you have any feedback or notice content on our platform that you believe violates these terms, please contact us.
        </p>
      </div>
    ),
  },
] as const;

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />

      {/* Hero Header */}
      <section className="relative border-b border-ink/10">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 md:py-24">
          <div className="grid gap-8 md:grid-cols-12 md:items-start">
            <Reveal className="md:col-span-5">
              <p className="text-[13px] font-mono tracking-wider text-muted uppercase">
                Legal Terms
              </p>
              <h1 className="mt-4 font-display text-[38px] font-semibold leading-[1.05] tracking-[-0.035em] text-ink sm:text-[48px] md:text-[58px]">
                Terms of Service
              </h1>
              <p className="mt-4 text-xs text-muted font-mono">
                LAST REVISED: MAY 2026
              </p>
            </Reveal>

            <Reveal
              delay={120}
              className="text-base leading-relaxed text-ink/75 md:col-span-6 md:col-start-7 md:pt-10 md:text-lg"
            >
              <p className="font-display text-xl font-medium tracking-tight text-ink sm:text-2xl">
                Please read these terms carefully before using Highlander Hub. Since we aggregate public event data, here is what we guarantee, what we expect, and where responsibilities lie.
              </p>
            </Reveal>
          </div>
        </div>
      </section>

      {/* Highlights Dashboard Component */}
      <section className="bg-surface border-b border-ink/10">
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
          <Reveal>
            <div className="grid gap-6 sm:grid-cols-3">
              {STATS_CARD.map((card) => (
                <div
                  key={card.label}
                  className="rounded-xl border border-ink/10 bg-canvas p-6 shadow-card hover:shadow-cardHover transition-shadow"
                >
                  <p className="text-sm font-medium text-muted">{card.label}</p>
                  <p className="mt-2 font-display text-3xl font-semibold tracking-tight text-ink">
                    {card.value}
                  </p>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* Terms Details Grid */}
      <section>
        <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 md:py-20">
          <div className="grid gap-10 lg:grid-cols-12 lg:items-start">
            {/* Quick Navigation Sticky Sidebar */}
            <aside className="hidden lg:sticky lg:top-24 lg:col-span-4 lg:block">
              <Reveal>
                <div className="rounded-xl border border-ink/10 bg-surface p-6">
                  <h2 className="font-display text-sm font-semibold uppercase tracking-wider text-muted">
                    Quick Navigation
                  </h2>
                  <nav className="mt-4">
                    <ul className="space-y-3 text-sm">
                      {TERMS_SECTIONS.map((sec) => (
                        <li key={sec.id}>
                          <a
                            href={`#${sec.id}`}
                            className="interactive-focus block py-1 font-medium text-ink/70 transition-colors hover:text-ink hover:underline underline-offset-4"
                          >
                            {sec.title.substring(3)}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </nav>
                  <div className="mt-6 border-t border-ink/10 pt-6">
                    <p className="text-xs leading-relaxed text-muted">
                      Have questions or need to dispute an event submission?
                    </p>
                    <Link
                      href="https://www.instagram.com/hbi.ucr"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="interactive-focus mt-3 inline-flex items-center gap-1 text-xs font-semibold text-ink hover:underline"
                    >
                      Instagram @hbi.ucr ↗
                    </Link>
                  </div>
                </div>
              </Reveal>
            </aside>

            {/* Main Terms Content Column */}
            <div className="space-y-12 lg:col-span-8 lg:col-start-5">
              {TERMS_SECTIONS.map((section, idx) => (
                <div key={section.id} id={section.id} className="scroll-mt-24">
                  <Reveal delay={idx * 50}>
                    <div>
                      <h2 className="font-display text-2xl font-semibold tracking-tight text-ink md:text-3xl">
                        {section.title}
                      </h2>
                      <div className="mt-4 text-sm leading-relaxed text-ink/75 sm:text-base">
                        {section.body}
                      </div>
                    </div>
                  </Reveal>
                  {idx < TERMS_SECTIONS.length - 1 && (
                    <div className="mt-12 h-[1px] w-full bg-ink/10" aria-hidden="true" />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
