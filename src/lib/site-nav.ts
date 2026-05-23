export const SITE_NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/events", label: "Events" },
  { href: "/about", label: "About" },
  { href: "/submit", label: "Submit" },
] as const;

export const MASTHEAD_NAV_LINKS = SITE_NAV_LINKS.filter(
  (link) => link.href !== "/"
);
