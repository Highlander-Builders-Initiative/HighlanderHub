export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ??
  "https://highlanderhub.app";

export const SITE_NAME = "Highlander Hub";
export const SITE_TITLE = "Highlander Hub · UCR & Riverside Events";
export const SITE_DESCRIPTION =
  "Campus and club events at UC Riverside and around the city, in one clean feed.";
export const SITE_PREVIEW_IMAGE = "/logo_icon.png";

export function absoluteUrl(path: string): string {
  return new URL(path, SITE_URL).toString();
}
