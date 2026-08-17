"use client";

import type { ReactNode } from "react";
import { ThemeProvider } from "./theme-provider";
import { MotionProvider } from "./motion-provider";
import { QueryProvider } from "./query-provider";

/**
 * Composition root for global client providers, mounted once in app/layout.tsx.
 * Order (outer → inner): Theme → Query → Motion. Query was added in Sprint 17.2
 * to power auth mutations against the mock service adapter.
 */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryProvider>
        <MotionProvider>{children}</MotionProvider>
      </QueryProvider>
    </ThemeProvider>
  );
}
