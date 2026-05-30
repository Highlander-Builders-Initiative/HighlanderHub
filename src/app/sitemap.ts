import type { MetadataRoute } from "next";
import { getSitemapEvents } from "@/lib/events";
import { SITE_URL, absoluteUrl } from "@/lib/seo";

const routes = ["", "/events", "/about", "/submit", "/privacy", "/terms"];

export const dynamic = "force-dynamic";

function safeDate(value: string): Date | undefined {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const staticRoutes = routes.map((route) => ({
    url: `${SITE_URL}${route}`,
    lastModified: now,
    changeFrequency:
      route === "" || route === "/events"
        ? ("daily" as const)
        : ("monthly" as const),
    priority: route === "" ? 1 : route === "/events" ? 0.9 : 0.6,
  }));

  const eventRoutes = (await getSitemapEvents()).map((event) => ({
    url: absoluteUrl(`/events/${event.id}`),
    lastModified: safeDate(event.lastModified) ?? now,
    changeFrequency: "daily" as const,
    priority: 0.7,
  }));

  return [...staticRoutes, ...eventRoutes];
}
