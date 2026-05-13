import { FaDiscord, FaInstagram, FaLinkedin } from "react-icons/fa";

const socialLinks = [
  {
    label: "Instagram",
    href: "https://www.instagram.com/hbi.ucr",
    Icon: FaInstagram,
  },
  {
    label: "Discord",
    href: "https://discord.com/invite/QYCQwTTvfS",
    Icon: FaDiscord,
  },
  {
    label: "LinkedIn",
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
          <h3 className="mb-3 text-sm font-semibold text-ink">Status</h3>
          <p className="text-sm text-muted">
            Placeholder data. No live scrape yet.
          </p>
          <p className="mt-2 text-sm text-muted">
            Built by Highlander Builders Initiative
          </p>
        </div>
      </div>
      <div className="border-t border-ink/10">
        <div className="mx-auto flex max-w-7xl flex-col items-center gap-4 px-4 py-5 text-xs text-muted sm:flex-row sm:justify-between sm:px-6">
          <p>© {new Date().getFullYear()} Highlander Hub · Not affiliated with UCR</p>
          <div className="flex items-center gap-3 text-ink" aria-label="Social links">
            {socialLinks.map(({ Icon, href, label }) => (
              <a
                key={label}
                href={href}
                aria-label={label}
                target="_blank"
                rel="noopener noreferrer"
                className="interactive-focus flex h-11 w-11 items-center justify-center transition-opacity hover:opacity-70"
              >
                <Icon aria-hidden="true" className="h-6 w-6" />
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
