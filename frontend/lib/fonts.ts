import { Inter, JetBrains_Mono } from "next/font/google";

/**
 * Brand typefaces, wired to the CSS variables the design system expects
 * (`--font-sans`, `--font-mono` — see styles/globals.css and tailwind.config.ts).
 * Applied on <html> in app/layout.tsx.
 */
export const fontSans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const fontMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});
