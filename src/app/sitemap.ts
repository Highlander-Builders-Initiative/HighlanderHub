import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/seo";

const routes = ["", "/events", "/about", "/submit"];

export default function sitemap(): MetadataRoute.Sitemap {
  return routes.map((route) => ({
    url: `${SITE_URL}${route}`,
    lastModified: new Date(),
    changeFrequency: route === "" || route === "/events" ? "daily" : "monthly",
    priority: route === "" ? 1 : route === "/events" ? 0.9 : 0.6,
  }));
}
