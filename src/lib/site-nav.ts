export type SiteNavLink = { href: string; label: string };

export const SITE_NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/events", label: "Events" },
  { href: "/about", label: "About" },
  { href: "/submit", label: "Submit" },
] as const;

export const MASTHEAD_NAV_LINKS = SITE_NAV_LINKS.filter(
  (link) => link.href !== "/"
);

// The /events top bar carries Home, About and Submit directly (the left rail
// no longer owns site navigation). "Events" is dropped because it is the
// current page.
export const EVENTS_NAV_LINKS = SITE_NAV_LINKS.filter(
  (link) => link.href !== "/events"
);
