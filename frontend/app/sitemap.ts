import type { MetadataRoute } from "next";

import { siteConfig } from "@/lib/site-config";

/**
 * sitemap.xml (Next.js metadata route).
 *
 * Only the publicly indexable routes: the marketing landing page and the two
 * public entry points (sign in / sign up). Everything else lives behind auth and
 * is excluded here and in robots.ts.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  return [
    {
      url: siteConfig.url,
      lastModified,
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: `${siteConfig.url}/login`,
      lastModified,
      changeFrequency: "monthly",
      priority: 0.5,
    },
    {
      url: `${siteConfig.url}/signup`,
      lastModified,
      changeFrequency: "monthly",
      priority: 0.8,
    },
  ];
}
