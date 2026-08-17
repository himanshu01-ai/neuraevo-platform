import type { MetadataRoute } from "next";

import { siteConfig } from "@/lib/site-config";

/**
 * robots.txt (Next.js metadata route).
 *
 * The public marketing surface is crawlable; the authenticated application and
 * transactional/token-bearing pages are not — search engines should never index
 * a user's workspace, a voice session, or a reset/verify link. Points crawlers
 * at the sitemap for the public routes.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        "/workspace/",
        "/voice/",
        "/onboarding",
        "/collaboration/",
        "/reset-password",
        "/verify-email",
        "/forgot-password",
      ],
    },
    sitemap: `${siteConfig.url}/sitemap.xml`,
    host: siteConfig.url,
  };
}
