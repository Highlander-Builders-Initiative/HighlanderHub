import type { Metadata } from "next";
import { LegalDocumentLayout } from "@/components/layout/LegalDocumentLayout";
import { HBI_ABOUT_URL } from "@/lib/hbi";

export const metadata: Metadata = {
  title: "Terms of Service · Highlander Hub",
  description: "Official Terms of Service for Highlander Hub. Details on user agreement, non-affiliation, and content disclaimers.",
};

export default function TermsPage() {
  return (
    <LegalDocumentLayout
      kicker="Legal & Terms Documentation"
      title="Highlander Hub Terms of Service"
      revisedDate="MAY 26, 2026"
    >

      {/* Introduction */}
      <section className="mt-8 space-y-4 text-base text-ink/80 leading-relaxed">
        <p>
          Welcome to Highlander Hub. By accessing or using our website, database directory, or submission tools (collectively, the &ldquo;Service&rdquo;), developed and operated by the{" "}
          <a
            href={HBI_ABOUT_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-ink underline decoration-ink/20 underline-offset-4 hover:decoration-ink"
          >
            Highlander Builders Initiative (HBI)
          </a>
          , you agree to be bound by these Terms of Service.
        </p>
        <p>
          If you do not agree to these terms, you are prohibited from using the Service. We reserve the right to revise or update these terms at our discretion, and your continued usage of Highlander Hub represents your agreement to the modified terms.
        </p>
      </section>

      {/* Policy Body */}
      <div className="mt-12 space-y-10 text-base text-ink/80 leading-relaxed">
        
        {/* Section 1 */}
        <section className="scroll-mt-24">
          <h2 className="font-display text-xl font-bold tracking-tight text-ink border-b border-ink/10 pb-2">
            1. Non-Affiliation Statement
          </h2>
          <div className="mt-4 space-y-4">
            <p className="font-semibold text-ink">
              Highlander Hub is a student-built directory developed independently by members of the Highlander Builders Initiative. We are not officially affiliated with, endorsed by, sponsored by, or connected to the University of California, Riverside (UCR) or the Regents of the University of California.
            </p>
            <p>
              Any references to UCR, campus facilities, official student organizations, or university events are conducted purely for the purpose of informing the campus student body.
            </p>
          </div>
        </section>

        {/* Section 2 */}
        <section className="scroll-mt-24">
          <h2 className="font-display text-xl font-bold tracking-tight text-ink border-b border-ink/10 pb-2">
            2. Event Content Disclaimer
          </h2>
          <div className="mt-4 space-y-4">
            <p>
              Because Highlander Hub aggregates event data automatically from public feeds and relies on crowdsourced submissions:
            </p>
            <ul className="list-disc pl-5 space-y-2">
              <li>
                We provide all event listings and metadata on an &ldquo;as is&rdquo; and &ldquo;as available&rdquo; basis.
              </li>
              <li>
                We do not guarantee the correctness, accuracy, completeness, or reliability of any listings (including event times, titles, locations, fees, or cancellation status).
              </li>
              <li>
                Organizations can change event locations or schedules without notice. We are not responsible for any inaccuracies, and users are strongly advised to check the hosting organization&rsquo;s official social channels before attending.
              </li>
            </ul>
          </div>
        </section>

        {/* Section 3 */}
        <section className="scroll-mt-24">
          <h2 className="font-display text-xl font-bold tracking-tight text-ink border-b border-ink/10 pb-2">
            3. Event Submissions & Licensing
          </h2>
          <div className="mt-4 space-y-4">
            <p>
              When submitting event details, images, or metadata using our submission form, you agree to the following conditions:
            </p>
            <ul className="list-disc pl-5 space-y-2">
              <li>
                <strong>Ownership Rights:</strong> You or your student organization retain the copyright and any other rights you already hold in the event details and flyer graphics.
              </li>
              <li>
                <strong>Granted License:</strong> You grant Highlander Builders Initiative a worldwide, royalty-free, non-exclusive, perpetual, and transferable license to host, resize, modify, crop, publish, and display the event listing on our platform.
              </li>
              <li>
                <strong>Representations:</strong> You represent and warrant that you hold all necessary permissions and rights to authorize this listing, and that the upload does not infringe upon any third-party intellectual property or copyright.
              </li>
            </ul>
            <p>
              We reserve the complete right to moderate, edit, or remove any submission at our sole discretion, without notice, if we believe the content violates campus guidelines, contains spam, or is otherwise inappropriate.
            </p>
          </div>
        </section>

        {/* Section 4 */}
        <section className="scroll-mt-24">
          <h2 className="font-display text-xl font-bold tracking-tight text-ink border-b border-ink/10 pb-2">
            4. Intellectual Property & Fair Use
          </h2>
          <div className="mt-4 space-y-4">
            <p>
              The custom source code, programmatic design, user interface layout, database indexes, and custom graphics of Highlander Hub are the sole property of the Highlander Builders Initiative.
            </p>
            <p>
              Student organization flyers, brand logos, and media graphics are the property of their respective copyright holders. We host and display these promotional graphics purely for public information, community commentary, and non-commercial educational purposes under the provisions of the **Fair Use** doctrine.
            </p>
          </div>
        </section>

        {/* Section 5 */}
        <section className="scroll-mt-24">
          <h2 className="font-display text-xl font-bold tracking-tight text-ink border-b border-ink/10 pb-2">
            5. Limitation of Liability
          </h2>
          <div className="mt-4 space-y-4">
            <p>
              TO THE FULLEST EXTENT PERMITTED BY APPLICABLE LAW, THE HIGHLANDER BUILDERS INITIATIVE, ITS PROJECT TEAM MEMBERS, AND CONTRIBUTORS SHALL NOT BE LIABLE FOR ANY DIRECT, INDIRECT, CONSEQUENTIAL, INCIDENTAL, SPECIAL, OR PUNITIVE DAMAGES ARISING FROM:
            </p>
            <ul className="list-disc pl-5 space-y-1">
              <li>YOUR ACCESS TO OR INABILITY TO USE THE SERVICE.</li>
              <li>ANY INACCURACIES, ERROR, OR FAULTS IN THE DIRECTORY LISTINGS.</li>
              <li>YOUR ATTENDANCE OR PARTICIPATION IN ANY EVENT FOUND ON THE PLATFORM.</li>
              <li>THE CONDUCT OF ANY THIRD-PARTY STUDENT ORGANIZATION OR HOST.</li>
            </ul>
          </div>
        </section>

        {/* Section 6 */}
        <section className="scroll-mt-24">
          <h2 className="font-display text-xl font-bold tracking-tight text-ink border-b border-ink/10 pb-2">
            6. System Abuse & Service Discontinuation
          </h2>
          <div className="mt-4 space-y-4">
            <p>
              Users are prohibited from trying to scrape our platform excessively, inject harmful scripts, or submit false event records. We reserve the right to restrict submission capabilities or block IP ranges/domains if we detect malicious usage.
            </p>
            <p>
              We reserve the right to modify, suspend, or terminate Highlander Hub, or any portion of the Service, at any time without notice or liability.
            </p>
            <p>
              If you have questions about these terms or wish to report content, please contact us at:
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

      </div>
    </LegalDocumentLayout>
  );
}
