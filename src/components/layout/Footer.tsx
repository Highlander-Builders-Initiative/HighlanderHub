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

export function Footer() {
  return (
    <footer id="about" className="mt-16 border-t border-ink/10">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-2">
        <div>
          <p className="font-display text-xl font-semibold tracking-[-0.04em] text-ink">
            highlander<span className="text-muted">/</span>hub
          </p>
          <p className="mt-3 max-w-md text-sm text-muted">
            A simple place to see what&rsquo;s happening at UC Riverside, without scrolling ten pages.
          </p>
        </div>
        <div className="md:text-right">
          <p className="text-sm text-muted">
            Built by Highlander Builders Initiative
          </p>
        </div>
      </div>
      <div className="border-t border-ink/10">
        <div className="mx-auto flex max-w-7xl flex-col items-center gap-4 px-4 py-5 text-xs text-muted sm:flex-row sm:justify-between sm:px-6">
          <p>© {new Date().getFullYear()} Highlander Hub · Not affiliated with UCR</p>
          <div className="flex items-center gap-3 text-ink" aria-label="Social links">
            {socialLinks.map(({ Icon, href, label, channel }) => (
              <HbiLink
                key={label}
                href={href}
                ariaLabel={label}
                location="footer_social"
                channel={channel}
                className="interactive-focus flex h-11 w-11 items-center justify-center rounded-full text-ink transition-colors hover:bg-ink/5"
              >
                <Icon aria-hidden="true" className="h-6 w-6" />
              </HbiLink>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
