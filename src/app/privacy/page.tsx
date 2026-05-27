import type { Metadata } from "next";
import { Masthead } from "@/components/layout/Masthead";
import { HBI_ABOUT_URL } from "@/lib/hbi";
import { Footer } from "@/components/layout/Footer";

export const metadata: Metadata = {
  title: "Privacy Policy · Highlander Hub",
  description: "Official Privacy Policy for Highlander Hub. Details on event data aggregation, submission handling, and cookie policies.",
};

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />

      <article className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16 md:py-20">
        {/* Document Header */}
        <header className="border-b border-ink/10 pb-6">
          <p className="text-xs font-mono tracking-wider text-muted uppercase">
            Legal & Privacy Documentation
          </p>
          <h1 className="mt-2 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            Highlander Hub Privacy Policy
          </h1>
          <p className="mt-2 text-xs text-muted font-mono">
            LAST REVISED: MAY 26, 2026
          </p>
        </header>

        {/* Introduction */}
        <section className="mt-8 space-y-4 text-base text-ink/80 leading-relaxed">
          <p>
            Highlander Hub (&ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo;) is an independent student-led directory developed by the{" "}
            <a
              href={HBI_ABOUT_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-ink underline decoration-ink/20 underline-offset-4 hover:decoration-ink"
            >
              Highlander Builders Initiative (HBI)
            </a>
            . We provide a single, public index of campus and club events for the UC Riverside community.
          </p>
          <p>
            This Privacy Policy describes how we aggregate, receive, and manage information on the Highlander Hub website. By accessing or using the website, you agree to the collection and use of information in accordance with this policy.
          </p>
        </section>

        {/* Policy Body */}
        <div className="mt-12 space-y-10 text-base text-ink/80 leading-relaxed">
          
          {/* Section 1 */}
          <section className="scroll-mt-24">
            <h2 className="font-display text-xl font-bold tracking-tight text-ink border-b border-ink/10 pb-2">
              1. Information Aggregation & Crawling
            </h2>
            <div className="mt-4 space-y-4">
              <p>
                To provide a comprehensive directory of UC Riverside events, our automated data pipeline indexes publicly available information. The sources we monitor include:
              </p>
              <ul className="list-disc pl-5 space-y-2">
                <li>
                  <strong>Public Student Organization Channels:</strong> We parse promotional flyers and text descriptions posted publicly on Instagram stories and posts by registered student organizations. This aggregation includes event titles, schedules, locations, and hosting handle names.
                </li>
                <li>
                  <strong>Official University Feeds:</strong> We mirror public listings from UCR&rsquo;s official events directory (<code>events.ucr.edu</code>).
                </li>
                <li>
                  <strong>HighlanderLink:</strong> We monitor public student organization events listed on UCR&rsquo;s HighlanderLink platform.
                </li>
              </ul>
              <p>
                This automated processing is conducted purely to consolidate public campus announcements. original flyer graphics are indexed and displayed to provide accurate visual context for student discoverability.
              </p>
            </div>
          </section>

          {/* Section 2 */}
          <section className="scroll-mt-24">
            <h2 className="font-display text-xl font-bold tracking-tight text-ink border-b border-ink/10 pb-2">
              2. Manual Event Submissions
            </h2>
            <div className="mt-4 space-y-4">
              <p>
                If you choose to submit an event manually through our submission form, we collect the details provided during that submission. This information consists of:
              </p>
              <ul className="list-disc pl-5 space-y-2">
                <li><strong>Event Particulars:</strong> Event title, host organization, time, exact location, and text description.</li>
                <li><strong>Media Assets:</strong> Digital flyers or promotional graphics uploaded to represent the event.</li>
                <li><strong>Verification Info:</strong> A contact handle or email address, utilized solely by our moderation team to verify submission authenticity or clarify event specifics.</li>
              </ul>
              <p>
                Manual submissions are voluntary. Submitter contact details are kept strictly internal and are never shared with external agencies, marketing networks, or commercial third parties.
              </p>
            </div>
          </section>

          {/* Section 3 */}
          <section className="scroll-mt-24">
            <h2 className="font-display text-xl font-bold tracking-tight text-ink border-b border-ink/10 pb-2">
              3. Data Storage & Security
            </h2>
            <div className="mt-4 space-y-4">
              <p>
                All processed event data, submission details, and promotional media are hosted on secure database instances managed via Supabase. We implement standard access controls and operational safeguards to protect submission records from unauthorized access, modification, or disclosure.
              </p>
              <p>
                Because our platform functions as a public directory, any event detail you submit for listing (such as the event time, description, location, or promotional flyer) is intentionally made visible to the general public.
              </p>
            </div>
          </section>

          {/* Section 4 */}
          <section className="scroll-mt-24">
            <h2 className="font-display text-xl font-bold tracking-tight text-ink border-b border-ink/10 pb-2">
              4. Cookies & Web Analytics
            </h2>
            <div className="mt-4 space-y-4">
              <p>
                To maintain site reliability, identify broken links, and measure responsiveness, we collect high-level, aggregate site analytics:
              </p>
              <ul className="list-disc pl-5 space-y-2">
                <li>
                  <strong>Anonymized Site Performance:</strong> We use Vercel Analytics to track generic page performance statistics. This is fully anonymized and does not track individual identities, personal browsing habits, or behavioral profiles across other sites.
                </li>
                <li>
                  <strong>Functional State:</strong> We store minimal functional state (like query filters or session variables) locally to enable page routing and event search functionality during your visit.
                </li>
              </ul>
            </div>
          </section>

          {/* Section 5 */}
          <section className="scroll-mt-24">
            <h2 className="font-display text-xl font-bold tracking-tight text-ink border-b border-ink/10 pb-2">
              5. Corrections, Takedowns, & Opt-Out Rights
            </h2>
            <div className="mt-4 space-y-4">
              <p>
                We respect the control that organizers have over their promotional content. If you are an authorized officer or organizer of a listed event, you have the right to request:
              </p>
              <ul className="list-disc pl-5 space-y-2">
                <li>Immediate correction of typographical errors or changed event details.</li>
                <li>Complete removal of a specific event listing or flyer from our database.</li>
                <li>Opting your student organization&rsquo;s public social feeds out of our automated aggregation system.</li>
              </ul>
              <p>
                To initiate any data correction or opt-out request, please contact our student development team. We process requests within 24 hours:
              </p>
              <ul className="list-disc pl-5 space-y-1 font-medium text-ink">
                <li>
                  Direct Message:{" "}
                  <a
                    href="https://www.instagram.com/hbi.ucr"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline decoration-ink/30 hover:decoration-ink transition-colors"
                  >
                    Instagram @hbi.ucr
                  </a>
                </li>
                <li>
                  Developer Channel:{" "}
                  <a
                    href="https://discord.com/invite/QYCQwTTvfS"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline decoration-ink/30 hover:decoration-ink transition-colors"
                  >
                    HBI Discord Server
                  </a>
                </li>
              </ul>
            </div>
          </section>

          {/* Section 6 */}
          <section className="scroll-mt-24">
            <h2 className="font-display text-xl font-bold tracking-tight text-ink border-b border-ink/10 pb-2">
              6. External Services & Affiliations
            </h2>
            <div className="mt-4 space-y-4">
              <p>
                Highlander Hub is a student-run project and is not affiliated with the University of California, Riverside (UCR) or any of its official administrative divisions.
              </p>
              <p>
                Our directory displays links to external platforms, student org accounts, registration sites, and official campus pages. We do not operate or control the privacy policies of these third-party platforms. Once you exit our website, your activity is subject to that platform&rsquo;s specific terms.
              </p>
            </div>
          </section>

        </div>
      </article>

      <Footer />
    </main>
  );
}
