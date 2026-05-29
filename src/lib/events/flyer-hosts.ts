// Mirrors images.remotePatterns in next.config.js. A flyer whose host matches
// here is served through the next/image optimizer; every other (arbitrary)
// HTTPS host renders via a plain <img> instead — the optimizer stays closed to
// avoid an open server-side image proxy. tests/flyer-host-allowlist.test.mjs
// cross-checks this against the real remotePatterns so the two can't drift.
const SUPABASE_HOST = (() => {
  try {
    return new URL(
      process.env.NEXT_PUBLIC_SUPABASE_URL ??
        "https://qyxlojftdtjasxhzyqil.supabase.co"
    ).hostname;
  } catch {
    return "qyxlojftdtjasxhzyqil.supabase.co";
  }
})();

export function isOptimizableFlyerHost(rawUrl: string): boolean {
  let url: URL;
  try {
    url = new URL(rawUrl);
  } catch {
    return false;
  }
  if (url.protocol !== "https:") return false;

  const { hostname, pathname } = url;

  // "*.cdninstagram.com" — any subdomain, but not the apex (matches Next).
  if (/\.cdninstagram\.com$/.test(hostname)) return true;

  if (
    hostname === "se-images.campuslabs.com" &&
    pathname.startsWith("/clink/images/")
  ) {
    return true;
  }

  if (hostname === "localist-images.azureedge.net") return true;

  if (
    hostname === SUPABASE_HOST &&
    pathname.startsWith("/storage/v1/object/public/submission-flyers/")
  ) {
    return true;
  }

  return false;
}
