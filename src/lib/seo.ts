export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ??
  "https://highlanderhub.app";

export const SITE_NAME = "Highlander Hub";
export const SITE_TITLE = "Highlander Hub · UCR Campus & Club Events";
export const SITE_DESCRIPTION =
  "Campus and club events at UC Riverside, pulled from club Instagram posts onto one page.";
export const SITE_PREVIEW_IMAGE = "/logo_icon.png";
/** The 1200x630 link-preview card (scripts/render-og-card.mjs). */
export const SITE_SOCIAL_CARD = {
  url: "/og-card.jpg",
  width: 1200,
  height: 630,
  alt: "Highlander Hub: Every UCR event, one page.",
} as const;

export function absoluteUrl(path: string): string {
  return new URL(path, SITE_URL).toString();
}
