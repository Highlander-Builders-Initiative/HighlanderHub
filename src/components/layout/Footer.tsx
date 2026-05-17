import Link from "next/link";
import { FaDiscord, FaInstagram, FaLinkedin } from "react-icons/fa";
import { HbiLink } from "@/components/analytics/HbiLink";

const socialLinks = [
  {
    label: "Instagram",
    channel: "instagram",
    href: "https://www.instagram.com/hbi.ucr",
    Icon: FaInstagram,
  },
  {
    label: "Discord",
    channel: "discord",
    href: "https://discord.com/invite/QYCQwTTvfS",
    Icon: FaDiscord,
  },
  {
    label: "LinkedIn",
    channel: "linkedin",
    href: "https://www.linkedin.com/company/hbi/",
    Icon: FaLinkedin,
  },
];

const siteLinks = [
  { label: "Events", href: "/events" },
  { label: "Submit", href: "/submit" },
  { label: "About", href: "/about" },
  { label: "Features", href: "/#features" },
];

export function Footer() {
  return (
    <footer className="mt-16 border-t border-ink/10">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-12 md:gap-8 md:py-14">
        {/* Brand */}
        <div className="md:col-span-5">
          <p className="font-display text-xl font-semibold tracking-[-0.04em] text-ink">
            highlander<span className="text-muted">/</span>hub
          </p>
          <p className="mt-3 max-w-md text-sm text-muted">
            A simple place to see what&rsquo;s happening at UC Riverside,
            without scrolling ten pages.
          </p>
        </div>

        {/* Site */}
        <nav aria-labelledby="footer-site" className="md:col-span-3">
          <p
            id="footer-site"
            className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted"
          >
            Site
          </p>
          <ul className="mt-4 space-y-2 text-sm">
            {siteLinks.map((l) => (
              <li key={l.href}>
                <Link
                  href={l.href}
                  className="interactive-focus text-ink/80 transition-colors hover:text-ink"
                >
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        {/* Connect */}
        <div className="md:col-span-4">
          <p
            id="footer-connect"
            className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted"
          >
            Connect
          </p>
          <div
            aria-labelledby="footer-connect"
            className="mt-3 flex items-center gap-2 text-ink"
          >
            {socialLinks.map(({ Icon, href, label, channel }) => (
              <HbiLink
                key={label}
                href={href}
                ariaLabel={label}
                location="footer_social"
                channel={channel}
                className="interactive-focus flex h-11 w-11 items-center justify-center rounded-lg border border-ink/15 text-ink transition-colors hover:border-ink hover:bg-ink hover:text-white"
              >
                <Icon aria-hidden="true" className="h-5 w-5" />
              </HbiLink>
            ))}
          </div>
          <p className="mt-4 text-sm text-muted">
            Built by{" "}
            <Link
              href="/about"
              className="interactive-focus font-medium text-ink underline-offset-4 hover:underline"
            >
              Highlander Builders Initiative
            </Link>
            .
          </p>
        </div>
      </div>

      <div className="border-t border-ink/10">
        <div className="mx-auto flex max-w-7xl flex-col items-start gap-2 px-4 py-5 text-xs text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>© {new Date().getFullYear()} Highlander Hub</p>
          <p>Not affiliated with UC Riverside.</p>
        </div>
      </div>
    </footer>
  );
}
