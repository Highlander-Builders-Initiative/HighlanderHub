export type SiteNavLink = { href: string; label: string };

// One set of top-bar links on every page; the current page is marked rather
// than dropped, so the bar never reshuffles between routes.
export const SITE_NAV_LINKS: readonly SiteNavLink[] = [
  { href: "/", label: "Home" },
  { href: "/events", label: "Events" },
  { href: "/about", label: "About" },
  { href: "/submit", label: "Submit" },
];

export function isNavLinkActive(href: string, pathname: string | null) {
  if (!pathname) return false;
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
