import type { Metadata } from "next";
import Link from "next/link";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { Reveal } from "@/components/ui/Reveal";

export const metadata: Metadata = {
  title: "Privacy Policy · Highlander Hub",
  description: "Learn how Highlander Hub aggregates event data, handles manual submissions, and protects student privacy.",
};

const STATS_CARD = [
  { label: "Accounts Required", value: "0" },
  { label: "Personal Tracking Cookies", value: "None" },
  { label: "Ad Networks or Monetization", value: "0%" },
] as const;

const POLICY_SECTIONS = [
  {
    id: "overview",
    title: "1. Project Mission & Scope",
    body: (
      <div className="space-y-4">
        <p>
          Highlander Hub is an independent, student-built directory developed by the{" "}
          <Link
            href="/about"
            className="font-medium text-ink underline decoration-ink/20 underline-offset-4 hover:decoration-ink"
          >
            Highlander Builders Initiative (HBI)
          </Link>
          . Our goal is to bring campus life into a single, clean bulletin board that any UC Riverside student can browse in seconds.
        </p>
        <p>
          Because we build for our own community, we treat your privacy the way we want ours treated. We do not require signups, we do not track individuals across the web, and we do not monetize this service.
        </p>
      </div>
    ),
  },
  {
    id: "data-aggregation",
    title: "2. Information We Aggregate & Crawl",
    body: (
      <div className="space-y-4">
        <p>
          To compile a comprehensive list of campus events, our pipeline automatically aggregates public information from several sources:
        </p>
        <ul className="list-disc pl-5 space-y-2 text-ink/80">
          <li>
            <strong>Public Student Org Feeds:</strong> We parse flyer images and text posted publicly on Instagram stories and posts by registered student organizations. This includes event titles, times, descriptions, and locations.
          </li>
          <li>
            <strong>Official Campus Calendars:</strong> We mirror public listings from UCR&rsquo;s official events directory (<code>events.ucr.edu</code>).
          </li>
          <li>
            <strong>HighlanderLink:</strong> We monitor public student org events listed on UCR&rsquo;s HighlanderLink platform.
          </li>
        </ul>
        <p>
          We parse flyer text using automated systems to index crucial details like time, place, and title. Original flyer images are displayed alongside event details so students can see the full visual context.
        </p>
      </div>
    ),
  },
  {
    id: "manual-submissions",
    title: "3. Manual Event Submissions",
    body: (
      <div className="space-y-4">
        <p>
          When an organization leader or student submits an event manually using our submission tool, we collect:
        </p>
        <ul className="list-disc pl-5 space-y-2 text-ink/80">
          <li><strong>Event Metadata:</strong> Title, date, time, location, hosting organization, and event description.</li>
          <li><strong>Media Uploads:</strong> Digital flyers or promotional graphics uploaded to illustrate the event.</li>
          <li><strong>Submitter Info:</strong> Contact information (such as an Instagram handle or email address) so we can clarify details or verify the submission.</li>
        </ul>
        <p>
          Submitting an event is entirely voluntary. Any personal details provided in the submission (like a contact email or handle) are used solely for verification and system operations, and are never shared with third-party marketers or advertisers.
        </p>
      </div>
    ),
  },
  {
    id: "analytics-and-cookies",
    title: "4. Usage Analytics & Cookies",
    body: (
      <div className="space-y-4">
        <p>
          We care about performance and load times. To keep the website fast and functional, we use minimal, privacy-respecting tools:
        </p>
        <ul className="list-disc pl-5 space-y-2 text-ink/80">
          <li>
            <strong>Vercel Analytics:</strong> We track high-level, anonymized statistics such as page loads, page views, and system response times. This tool does not store personal profiles or track you across other websites.
          </li>
          <li>
            <strong>Core Functionality:</strong> We use basic storage (such as temporary local variables or session state) purely to handle page routing, search queries, and event filter preferences during your session.
          </li>
        </ul>
      </div>
    ),
  },
  {
    id: "takedown-and-control",
    title: "5. Control, Corrections, & Takedown Requests",
    body: (
      <div className="space-y-4">
        <p>
          Since we aggregate public data, errors or changes can occur. We fully support your right to control your digital footprint.
        </p>
        <p>
          If you are a student organization officer or individual organizer and would like to:
        </p>
        <ul className="list-disc pl-5 space-y-2 text-ink/80">
          <li>Request a correction to event descriptions, times, or locations.</li>
          <li>Have a specific flyer image or entire event listing removed from our index.</li>
          <li>Opt your student organization&rsquo;s public Instagram handle out of our automated aggregation pipeline.</li>
        </ul>
        <p className="mt-4">
          Please reach out to us, and we will process your request promptly (usually within 24 hours). You can reach us via:
        </p>
        <div className="mt-3 flex flex-wrap gap-4 text-sm font-medium">
          <a
            href="https://www.instagram.com/hbi.ucr"
            target="_blank"
            rel="noopener noreferrer"
            className="interactive-focus inline-flex items-center gap-1.5 rounded-lg border border-ink px-4 py-2 hover:bg-ink hover:text-canvas transition-colors"
          >
            DM us on Instagram ↗
          </a>
          <a
            href="https://discord.com/invite/QYCQwTTvfS"
            target="_blank"
            rel="noopener noreferrer"
            className="interactive-focus inline-flex items-center gap-1.5 rounded-lg border border-ink px-4 py-2 hover:bg-ink hover:text-canvas transition-colors"
          >
            Join HBI Discord ↗
          </a>
        </div>
      </div>
    ),
  },
  {
    id: "external-services",
    title: "6. External Services & Affiliations",
    body: (
      <div className="space-y-4">
        <p>
          Highlander Hub contains links to external platforms (e.g., student organization Instagram pages, external registration websites, official UCR pages, and map locations).
        </p>
        <p>
          We are not affiliated with the University of California, Riverside, nor do we govern the privacy policies of external platforms. Once you follow a link off our website, your activity is governed by that service&rsquo;s privacy terms.
        </p>
      </div>
    ),
  },
] as const;

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />

      {/* Hero Header */}
      <section className="relative border-b border-ink/10">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 md:py-24">
          <div className="grid gap-8 md:grid-cols-12 md:items-start">
            <Reveal className="md:col-span-5">
              <p className="text-[13px] font-mono tracking-wider text-muted uppercase">
                Privacy & Data
              </p>
              <h1 className="mt-4 font-display text-[38px] font-semibold leading-[1.05] tracking-[-0.035em] text-ink sm:text-[48px] md:text-[58px]">
                Highlander Hub Privacy Policy
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
                We believe in simple, transparent utilities. We build this index to help UCR students navigate campus life, without collecting personal info or showing tracking ads.
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

      {/* Policy Details Grid */}
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
                      {POLICY_SECTIONS.map((sec) => (
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
                      Have questions or need to remove your organization&rsquo;s public event data?
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

            {/* Main Policy Content Column */}
            <div className="space-y-12 lg:col-span-8 lg:col-start-5">
              {POLICY_SECTIONS.map((section, idx) => (
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
                  {idx < POLICY_SECTIONS.length - 1 && (
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
