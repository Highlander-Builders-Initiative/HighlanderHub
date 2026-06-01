import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { FaDiscord, FaInstagram, FaLinkedin } from "react-icons/fa";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { Reveal } from "@/components/ui/Reveal";
import { SubmitEventCta } from "@/components/events/SubmitEventCta";
import { HbiLink } from "@/components/analytics/HbiLink";
import { AboutFaq } from "@/components/about/AboutFaq";
import { HBI_ABOUT_URL } from "@/lib/hbi";

export const metadata: Metadata = {
  title: "About · Highlander Hub",
  description:
    "What Highlander Hub is, where event listings come from, and who built it.",
};

const PRINCIPLES = [
  {
    title: "Always free to browse",
    body: "No paywalls. Core browsing stays open to everyone, no account required.",
  },
  {
    title: "Built by students",
    body: "Made by Highlander Builders Initiative, for the campus we're part of.",
  },
  {
    title: "Not affiliated with UCR",
    body: "Independent project. We pull from public sources and host submissions ourselves.",
  },
] as const;

const SOURCES = [
  {
    label: "Club Instagram stories",
    body: "Flyers posted by registered student orgs. We read the image to find the title, time, and place.",
  },
  {
    label: "events.ucr.edu",
    body: "UCR's official campus events calendar, mirrored so you don't check two places.",
  },
  {
    label: "highlanderlink.ucr.edu",
    body: "Public org and campus listings on UCR's Engage platform (HighlanderLink).",
  },
  {
    label: "Manual submissions",
    body: "Org leads use the submit form when something isn't in the feeds yet.",
  },
] as const;

const FAQS = [
  {
    id: "data-freshness",
    q: "How fresh is the data?",
    a: "Automated sources refresh every six hours. Manual submissions are reviewed before they go live, usually within a day.",
  },
  {
    id: "report-wrong-event",
    q: "How do I report a wrong event?",
    a: "DM @hbi.ucr on Instagram with the event link. Flyer details are read automatically, so mistakes happen; we'll fix yours.",
  },
  {
    id: "add-org-calendar",
    q: "Can my org's calendar be added as a regular source?",
    a: "Yes. DM @hbi.ucr with your org's handle and a public events page if you have one. We'll add you to the rotation.",
  },
] as const;

const HBI_INSTAGRAM = "https://www.instagram.com/hbi.ucr";
const HBI_DISCORD = "https://discord.com/invite/QYCQwTTvfS";

export default function AboutPage() {
  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />

      {/* About opener + principles */}
      <section className="bg-canvas border-b border-ink/10">
        <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 md:py-20">
          <div className="grid gap-10 md:grid-cols-12 md:items-start">
            <Reveal className="md:col-span-5">
              <h1 className="max-w-xl font-display text-[36px] font-semibold leading-[1.03] tracking-[-0.035em] text-ink sm:text-[46px] md:text-[56px]">
                Campus events are scattered across ten different feeds.
              </h1>
            </Reveal>
            <Reveal
              delay={120}
              className="space-y-4 text-base leading-relaxed text-ink/75 md:col-span-6 md:col-start-7 md:pt-11 md:text-lg"
            >
              <p>
                Half the events at UCR live in Instagram stories that disappear
                in 24 hours. The rest sit on events.ucr.edu, HighlanderLink, a
                few club sites, and the occasional wall flyer. To know
                what&rsquo;s actually happening on a given Thursday, you&rsquo;d
                follow dozens of accounts and check several calendars.
              </p>
              <p>
                Highlander Hub does that work in one place. We gather what clubs
                already post, clean up the details, and put everything on one
                page you can scan in thirty seconds.
              </p>
            </Reveal>
          </div>

          <ul className="mt-12 grid gap-8 border-t border-ink/10 pt-10 sm:grid-cols-3 sm:gap-6">
            {PRINCIPLES.map((p, i) => (
              <Reveal key={p.title} delay={i * 80} as="li">
                <h2 className="font-display text-lg font-semibold tracking-[-0.02em] text-ink">
                  {p.title}
                </h2>
                <p className="mt-1.5 text-sm leading-relaxed text-ink/70">
                  {p.body}
                </p>
              </Reveal>
            ))}
          </ul>
        </div>
      </section>

      {/* Where events come from */}
      <section className="bg-surface border-b border-ink/10">
        <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 md:py-20">
          <div className="md:grid md:grid-cols-12 md:gap-10">
            <Reveal className="md:col-span-4 md:pt-1">
              <h2 className="font-display text-3xl font-semibold leading-[1.1] tracking-[-0.03em] text-ink md:text-4xl">
                Where listings come from
              </h2>
              <p className="mt-3 text-sm text-ink/70 md:text-base">
                Four feeds, one bulletin.{" "}
                <Link
                  href="#faq"
                  className="interactive-focus font-medium text-ink underline decoration-ink/30 underline-offset-4 hover:decoration-ink"
                >
                  FAQ
                </Link>{" "}
                covers refresh timing and corrections.
              </p>
            </Reveal>

            <ul className="mt-8 divide-y divide-ink/10 md:col-span-8 md:mt-0">
              {SOURCES.map((s) => (
                <li key={s.label} className="py-5 sm:py-6">
                  <div className="min-w-0 flex-1">
                    <h3 className="font-display text-lg font-semibold tracking-[-0.02em] text-ink md:text-xl">
                      {s.label}
                    </h3>
                    <p className="mt-1 text-sm text-ink/70 md:text-base">
                      {s.body}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Who built it (HBI) */}
      <section className="bg-surface border-b border-ink/10">
        <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 md:py-20">
          <Reveal
            as="article"
            className="grid gap-6 md:grid-cols-[auto_1fr] md:items-center md:gap-10"
          >
            <Image
              src="/logo_icon.png"
              alt="Highlander Builders Initiative Logo"
              width={72}
              height={72}
              className="h-16 w-16 md:h-[72px] md:w-[72px]"
            />
            <div>
              <p className="text-[13px] font-mono tracking-wider text-muted uppercase">
                The Builders Behind Highlander Hub
              </p>
              <h2 className="mt-2 font-display text-3xl font-semibold leading-[1.1] tracking-[-0.035em] text-ink md:text-4xl">
                <HbiLink
                  href={HBI_ABOUT_URL}
                  location="about_page"
                  channel="website"
                  className="interactive-focus hover:text-ink/80"
                >
                  Highlander Builders Initiative (HBI)
                </HbiLink>
              </h2>
              <p className="mt-3 max-w-3xl text-base text-ink/75 leading-relaxed md:text-lg">
                HBI is a selective student organization at UC Riverside where technically skilled students collaborate on ambitious real-world projects. We bring together engineers and creatives to grow as innovators, while forming lasting relationships through our community.
              </p>
              <div className="mt-5 flex flex-wrap items-center gap-2">
                <HbiLink
                  href={HBI_INSTAGRAM}
                  location="about_page"
                  channel="instagram"
                  ariaLabel="HBI on Instagram"
                  className="interactive-focus inline-flex h-11 w-11 items-center justify-center rounded-lg border border-ink/15 text-ink transition-colors hover:border-ink hover:bg-ink hover:text-canvas"
                >
                  <FaInstagram aria-hidden className="h-5 w-5" />
                </HbiLink>
                <HbiLink
                  href={HBI_DISCORD}
                  location="about_page"
                  channel="discord"
                  ariaLabel="HBI on Discord"
                  className="interactive-focus inline-flex h-11 w-11 items-center justify-center rounded-lg border border-ink/15 text-ink transition-colors hover:border-ink hover:bg-ink hover:text-canvas"
                >
                  <FaDiscord aria-hidden className="h-5 w-5" />
                </HbiLink>
                <HbiLink
                  href="https://www.linkedin.com/company/hbi/"
                  location="about_page"
                  channel="linkedin"
                  ariaLabel="HBI on LinkedIn"
                  className="interactive-focus inline-flex h-11 w-11 items-center justify-center rounded-lg border border-ink/15 text-ink transition-colors hover:border-ink hover:bg-ink hover:text-canvas"
                >
                  <FaLinkedin aria-hidden className="h-5 w-5" />
                </HbiLink>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Get involved */}
      <section className="bg-canvas border-b border-ink/10">
        <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 md:py-20">
          <h2 className="font-display text-3xl font-semibold leading-[1.1] tracking-[-0.03em] text-ink md:text-4xl">
            Get involved
          </h2>

          <Reveal
            delay={80}
            as="div"
            className="mt-8 flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between sm:gap-10"
          >
            <div className="max-w-xl">
              <p className="font-display text-xl font-semibold tracking-[-0.02em] text-ink md:text-2xl">
                Submit an event
              </p>
              <p className="mt-2 text-sm text-ink/70 md:text-base">
                Running something this quarter? Add it through the bulletin
                form.
              </p>
            </div>
            <SubmitEventCta surface="about_page" />
          </Reveal>

          <ul className="mt-2 divide-y divide-ink/10">
            <Reveal delay={120} as="li" className="pb-6 pt-7">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between sm:gap-8">
                <div className="max-w-xl">
                  <p className="font-display text-lg font-semibold tracking-[-0.02em] text-ink">
                    Get your org listed
                  </p>
                  <p className="mt-1.5 text-sm text-ink/70 md:text-base">
                    Want your org&rsquo;s meetings and events pulled in
                    automatically? Message us on Instagram (see{" "}
                    <Link
                      href="#faq"
                      className="interactive-focus font-medium text-ink underline decoration-ink/30 underline-offset-4 hover:decoration-ink"
                    >
                      FAQ
                    </Link>
                    ).
                  </p>
                </div>
                <HbiLink
                  href={HBI_INSTAGRAM}
                  location="about_page"
                  channel="instagram"
                  className="interactive-focus inline-flex min-h-12 shrink-0 items-center gap-2 rounded-lg border border-ink bg-canvas px-5 py-3 text-sm font-medium text-ink transition-colors hover:bg-ink hover:text-canvas"
                >
                  DM @hbi.ucr
                  <span aria-hidden>↗</span>
                </HbiLink>
              </div>
            </Reveal>
            <Reveal delay={180} as="li" className="py-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between sm:gap-8">
                <div className="max-w-xl">
                  <p className="font-display text-lg font-semibold tracking-[-0.02em] text-ink">
                    Build with HBI
                  </p>
                  <p className="mt-1.5 text-sm text-ink/70 md:text-base">
                    We ship real tools for UCR students. Join the Discord to
                    see what we&rsquo;re working on next.
                  </p>
                </div>
                <HbiLink
                  href={HBI_DISCORD}
                  location="about_page"
                  channel="discord"
                  className="interactive-focus inline-flex min-h-12 shrink-0 items-center gap-2 rounded-lg border border-ink bg-canvas px-5 py-3 text-sm font-medium text-ink transition-colors hover:bg-ink hover:text-canvas"
                >
                  Join the Discord
                  <span aria-hidden>↗</span>
                </HbiLink>
              </div>
            </Reveal>
          </ul>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="bg-surface">
        <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 md:pb-24 md:pt-16">
          <Reveal className="max-w-2xl">
            <h2 className="font-display text-3xl font-semibold leading-[1.1] tracking-[-0.03em] text-ink md:text-4xl">
              Common questions
            </h2>
          </Reveal>

          <AboutFaq items={FAQS} />
        </div>
      </section>

      <Footer />
    </main>
  );
}
