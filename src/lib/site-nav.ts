export type SiteNavLink = { href: string; label: string };

// One set of top-bar links on every page; the current page is marked rather
// than dropped, so the bar never reshuffles between routes. The wordmark is
// the way home, so there is no Home link.
export const SITE_NAV_LINKS: readonly SiteNavLink[] = [
  { href: "/events", label: "Events" },
  { href: "/about", label: "About" },
];

export function isNavLinkActive(href: string, pathname: string | null) {
  if (!pathname) return false;
  return pathname === href || pathname.startsWith(`${href}/`);
}
