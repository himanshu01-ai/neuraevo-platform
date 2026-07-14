"use client";

import type { ReactNode } from "react";
import { ThemeProvider } from "./theme-provider";
import { MotionProvider } from "./motion-provider";

/**
 * Composition root for global client providers, mounted once in app/layout.tsx.
 * Order (outer → inner): Theme → Motion. No data/query provider — Sprint 17.1
 * has no backend integration.
 */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <MotionProvider>{children}</MotionProvider>
    </ThemeProvider>
  );
}
