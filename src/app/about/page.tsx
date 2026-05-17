import type { Metadata } from "next";
import Image from "next/image";
import { FaDiscord, FaInstagram, FaLinkedin } from "react-icons/fa";
import { Masthead } from "@/components/layout/Masthead";
import { Footer } from "@/components/layout/Footer";
import { Reveal } from "@/components/ui/Reveal";
import { SubmitEventCta } from "@/components/events/SubmitEventCta";
import { HbiLink } from "@/components/analytics/HbiLink";

export const metadata: Metadata = {
  title: "About · Highlander Hub",
  description:
    "What Highlander Hub is, where event listings come from, and who built it.",
};

const PRINCIPLES = [
  {
    kicker: "01",
    title: "Always free",
    body: "No paywalls, no accounts, no upsells. It's a student bulletin.",
  },
  {
    kicker: "02",
    title: "Built by students",
    body: "Made by the team at Highlander Builders Initiative, for the campus we're part of.",
  },
  {
    kicker: "03",
    title: "Not affiliated with UCR",
    body: "Independent project. We pull from public sources and host submissions ourselves.",
  },
];

const SOURCES = [
  {
    label: "Club Instagram stories",
    body: "Flyers posted by registered student orgs. We OCR the image and pull title, time, and location with help from an LLM.",
    dot: "bg-coral",
  },
  {
    label: "events.ucr.edu",
    body: "UCR's official campus events calendar. We mirror what's posted there so you don't have to check two places.",
    dot: "bg-highlander",
  },
  {
    label: "Manual submissions",
    body: "Org leads submit events through the bulletin's form. We review each one — usually within a day.",
    dot: "bg-leaf",
  },
];

const FAQS = [
  {
    q: "Is this affiliated with UC Riverside?",
    a: "No. Highlander Hub is an independent student project. We pull from public sources and host submissions ourselves. UCR is not involved in operating or moderating the bulletin.",
  },
  {
    q: "How fresh is the data?",
    a: "Updates run automatically every six hours, so anything posted in the last day usually shows up by the next refresh. Manual submissions get reviewed within a day.",
  },
  {
    q: "Can my org's calendar be added as a regular source?",
    a: "Yes. DM @hbi.ucr on Instagram with your org's handle (and a public events page if you have one) and we'll add you to the rotation.",
  },
  {
    q: "Is it free?",
    a: "Yes, and always will be. There are no plans to add ads, accounts, or paid tiers.",
  },
];

export default function AboutPage() {
  return (
    <main className="min-h-screen bg-canvas">
      <Masthead />

      {/* Hero */}
      <section className="border-b border-ink/10">
        <div className="mx-auto max-w-7xl px-4 pt-12 pb-16 sm:px-6 md:pt-20 md:pb-24">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
            About
          </p>
          <h1 className="mt-3 max-w-3xl font-display text-[36px] font-semibold leading-[1.05] tracking-[-0.03em] text-ink sm:text-[52px] md:text-[64px]">
            A bulletin for the campus,
            <span className="block text-muted">built by the campus.</span>
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-relaxed text-ink/75 md:text-lg">
            Highlander Hub is one place to find out what&rsquo;s actually
            happening at UC Riverside this week. Club meetings, free food drops,
            workshops, banquets, concerts — pulled from the sources clubs
            already use, so you don&rsquo;t have to follow forty Instagram
            accounts to know when the next general meeting is.
          </p>
        </div>
      </section>

      {/* Principles */}
      <section className="border-b border-ink/10">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 md:py-20">
          <div className="grid gap-4 md:grid-cols-3">
            {PRINCIPLES.map((p, i) => (
              <Reveal
                key={p.kicker}
                delay={i * 100}
                as="article"
                className="flex flex-col gap-2 rounded-xl border border-ink/15 bg-canvas p-6"
              >
                <span className="font-mono text-[11px] tracking-[0.14em] text-muted">
                  {p.kicker}
                </span>
                <h2 className="font-display text-xl font-semibold tracking-[-0.02em] text-ink">
                  {p.title}
                </h2>
                <p className="text-sm text-ink/70">{p.body}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Why it exists */}
      <section className="border-b border-ink/10">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-20 sm:px-6 md:grid-cols-12 md:py-28">
          <Reveal className="md:col-span-4">
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
              Why it exists
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold leading-[1.1] tracking-[-0.03em] text-ink md:text-4xl">
              Campus events are scattered across ten different feeds.
            </h2>
          </Reveal>
          <Reveal delay={120} className="space-y-4 text-base leading-relaxed text-ink/75 md:col-span-7 md:col-start-6 md:text-lg">
            <p>
              Half the events at UCR live in Instagram stories that disappear
              in 24 hours. The other half live on events.ucr.edu, a few club
              websites, the occasional flyer taped to a wall. To know what&rsquo;s
              actually happening on a given Thursday, you&rsquo;d have to follow
              dozens of accounts and check three different calendars.
            </p>
            <p>
              Highlander Hub does that work in one place. We pull from the
              sources clubs already use, normalize the details, and put it all
              on a single page you can scan in thirty seconds.
            </p>
          </Reveal>
        </div>
      </section>

      {/* Where events come from */}
      <section className="border-b border-ink/10">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 md:py-28">
          <Reveal className="max-w-2xl">
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
              Where events come from
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold leading-[1.1] tracking-[-0.03em] text-ink md:text-4xl">
              Three sources, one bulletin.
            </h2>
          </Reveal>

          <ul className="mt-10 divide-y divide-ink/10 border-y border-ink/10">
            {SOURCES.map((s) => (
              <li
                key={s.label}
                className="flex items-start gap-4 py-6 sm:gap-6 sm:py-7"
              >
                <span
                  aria-hidden
                  className={`mt-2 h-2 w-2 shrink-0 rounded-full ${s.dot}`}
                />
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

          <p className="mt-8 max-w-2xl text-sm text-muted">
            Updates run automatically every six hours. We extract event details
            from flyer images with OCR + an LLM, so the occasional misread
            happens — spot one and let us know.
          </p>
        </div>
      </section>

      {/* Who built it */}
      <section className="border-b border-ink/10">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 md:py-28">
          <Reveal className="max-w-2xl">
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
              Who built it
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold leading-[1.1] tracking-[-0.03em] text-ink md:text-4xl">
              A side project from HBI.
            </h2>
          </Reveal>

          <Reveal
            delay={120}
            as="article"
            className="mt-10 grid gap-6 rounded-xl border border-ink/15 bg-canvas p-6 sm:p-8 md:grid-cols-[auto_1fr] md:items-center md:gap-8"
          >
            <Image
              src="/logo_icon.png"
              alt=""
              width={72}
              height={72}
              aria-hidden
              className="h-16 w-16 md:h-[72px] md:w-[72px]"
            />
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
                Highlander Builders Initiative
              </p>
              <p className="mt-2 font-display text-xl font-semibold tracking-[-0.02em] text-ink md:text-2xl">
                A student org at UCR for people who like to build things.
              </p>
              <p className="mt-3 text-sm text-ink/70 md:text-base">
                Highlander Hub is one of a few projects we ship in our spare
                time. Want to come build with us? Say hi on any of the channels
                below.
              </p>
              <div className="mt-5 flex flex-wrap items-center gap-2">
                <HbiLink
                  href="https://www.instagram.com/hbi.ucr"
                  location="about_page"
                  channel="instagram"
                  ariaLabel="HBI on Instagram"
                  className="interactive-focus inline-flex h-11 w-11 items-center justify-center rounded-lg border border-ink/15 text-ink transition-colors hover:border-ink hover:bg-ink hover:text-white"
                >
                  <FaInstagram aria-hidden className="h-5 w-5" />
                </HbiLink>
                <HbiLink
                  href="https://discord.com/invite/QYCQwTTvfS"
                  location="about_page"
                  channel="discord"
                  ariaLabel="HBI on Discord"
                  className="interactive-focus inline-flex h-11 w-11 items-center justify-center rounded-lg border border-ink/15 text-ink transition-colors hover:border-ink hover:bg-ink hover:text-white"
                >
                  <FaDiscord aria-hidden className="h-5 w-5" />
                </HbiLink>
                <HbiLink
                  href="https://www.linkedin.com/company/hbi/"
                  location="about_page"
                  channel="linkedin"
                  ariaLabel="HBI on LinkedIn"
                  className="interactive-focus inline-flex h-11 w-11 items-center justify-center rounded-lg border border-ink/15 text-ink transition-colors hover:border-ink hover:bg-ink hover:text-white"
                >
                  <FaLinkedin aria-hidden className="h-5 w-5" />
                </HbiLink>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Get involved */}
      <section className="border-b border-ink/10">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 md:py-28">
          <Reveal className="max-w-2xl">
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
              Get involved
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold leading-[1.1] tracking-[-0.03em] text-ink md:text-4xl">
              Two easy ways in.
            </h2>
          </Reveal>

          <div className="mt-10 grid gap-4 md:grid-cols-2">
            <Reveal
              as="article"
              className="flex flex-col gap-3 rounded-xl border border-ink/15 bg-canvas p-6"
            >
              <span className="font-mono text-[11px] tracking-[0.14em] text-muted">
                For org leads
              </span>
              <h3 className="font-display text-xl font-semibold tracking-[-0.02em] text-ink">
                Submit an event.
              </h3>
              <p className="text-sm text-ink/70">
                Running something this quarter? Drop the details and we&rsquo;ll
                review within a day.
              </p>
              <div className="mt-2">
                <SubmitEventCta surface="about_page" />
              </div>
            </Reveal>

            <Reveal
              delay={100}
              as="article"
              className="flex flex-col gap-3 rounded-xl border border-ink/15 bg-canvas p-6"
            >
              <span className="font-mono text-[11px] tracking-[0.14em] text-muted">
                For everyone else
              </span>
              <h3 className="font-display text-xl font-semibold tracking-[-0.02em] text-ink">
                Follow HBI.
              </h3>
              <p className="text-sm text-ink/70">
                Behind the scenes on Highlander Hub and the other things we
                ship. New builders welcome.
              </p>
              <div className="mt-2">
                <HbiLink
                  href="https://www.instagram.com/hbi.ucr"
                  location="about_page"
                  channel="instagram"
                  className="interactive-focus inline-flex min-h-12 items-center gap-2 rounded-lg border border-ink bg-canvas px-5 py-3 text-sm font-medium text-ink transition-colors hover:bg-ink hover:text-white"
                >
                  Follow @hbi.ucr
                  <span aria-hidden>↗</span>
                </HbiLink>
              </div>
            </Reveal>
          </div>

          <p className="mt-6 text-sm text-muted">
            Want your org&rsquo;s calendar added as a regular source? DM{" "}
            <HbiLink
              href="https://www.instagram.com/hbi.ucr"
              location="about_page"
              channel="instagram"
              className="interactive-focus font-medium text-ink underline-offset-4 hover:underline"
            >
              @hbi.ucr
            </HbiLink>{" "}
            on Instagram.
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section>
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 md:py-28">
          <Reveal className="max-w-2xl">
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
              FAQ
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold leading-[1.1] tracking-[-0.03em] text-ink md:text-4xl">
              Common questions.
            </h2>
          </Reveal>

          <dl className="mt-10 divide-y divide-ink/10 border-y border-ink/10">
            {FAQS.map((f) => (
              <details
                key={f.q}
                className="group py-5 [&_summary::-webkit-details-marker]:hidden"
              >
                <summary className="interactive-focus flex cursor-pointer items-center justify-between gap-6 list-none">
                  <dt className="font-display text-base font-semibold tracking-[-0.01em] text-ink md:text-lg">
                    {f.q}
                  </dt>
                  <span
                    aria-hidden
                    className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-ink/15 text-ink transition-transform group-open:rotate-45"
                  >
                    <svg
                      viewBox="0 0 20 20"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="h-4 w-4"
                    >
                      <path d="M10 4v12M4 10h12" />
                    </svg>
                  </span>
                </summary>
                <dd className="mt-3 max-w-3xl pr-14 text-sm leading-relaxed text-ink/75 md:text-base">
                  {f.a}
                </dd>
              </details>
            ))}
          </dl>
        </div>
      </section>

      <Footer />
    </main>
  );
}
