/**
 * NeuraEvo Design System — Color Tokens
 *
 * Single source of truth for raw color values (design reference).
 * Runtime theming is driven by CSS variables in `styles/globals.css`;
 * these constants exist for non-CSS contexts (Framer Motion, Canvas,
 * React Three Fiber, charts) and to document the canonical palette.
 *
 * Rule: never hardcode a hex in a component. Consume the CSS variable
 * (`bg-background`, `text-primary`, …) or import from here.
 */

/** Cool near-neutral gray ramp. The structural backbone of every surface. */
export const neutral = {
  0: "#FFFFFF",
  25: "#FCFCFD",
  50: "#F7F8FA",
  100: "#EEF0F3",
  200: "#E2E5EA",
  300: "#CBD0D9",
  400: "#9AA2B1",
  500: "#6B7280",
  600: "#4B5563",
  700: "#363B45",
  800: "#22262E",
  900: "#14171C",
  950: "#0B0D11",
  1000: "#060709",
} as const;

/** NeuraEvo Violet — the single, confident brand accent. */
export const brand = {
  50: "#EEF0FF",
  100: "#E0E3FF",
  200: "#C6CBFF",
  300: "#A3A8FF",
  400: "#7E7DFF",
  500: "#6C5CF2", // primary — official NeuraEvo logo violet
  600: "#514BE0",
  700: "#423CBD",
  800: "#363199",
  900: "#2B2878",
  950: "#1A1852",
} as const;

/** Semantic ramps. Each maps to backend state vocabulary (see types/domain.ts). */
export const semantic = {
  /** COMPLETED · APPROVED · HEALTHY */
  success: { soft: "#D1FADF", base: "#10B981", strong: "#047857", fg: "#FFFFFF" },
  /** PAUSED · PENDING · DEGRADED */
  warning: { soft: "#FEF0C7", base: "#F59E0B", strong: "#B45309", fg: "#1A1205" },
  /** FAILED · REJECTED · UNHEALTHY */
  danger: { soft: "#FEE4E2", base: "#EF4444", strong: "#B42318", fg: "#FFFFFF" },
  /** RUNNING · QUEUED · INFO */
  info: { soft: "#D1E9FF", base: "#3B82F6", strong: "#1D4ED8", fg: "#FFFFFF" },
  /** CANCELLED · IDLE · DISABLED */
  neutral: { soft: "#EEF0F3", base: "#6B7280", strong: "#363B45", fg: "#FFFFFF" },
} as const;

/**
 * The shadcn/ui variable contract, expressed as space-separated HSL triplets
 * (the format Tailwind consumes via `hsl(var(--token))`). Mirrored 1:1 in
 * `styles/globals.css`. Keep the two in sync — this object is the reference.
 */
export const themeVars = {
  light: {
    background: "210 20% 99%",
    foreground: "222 24% 11%",
    card: "0 0% 100%",
    "card-foreground": "222 24% 11%",
    popover: "0 0% 100%",
    "popover-foreground": "222 24% 11%",
    primary: "246 85% 65%",
    "primary-foreground": "0 0% 100%",
    secondary: "214 16% 96%",
    "secondary-foreground": "222 20% 20%",
    muted: "214 16% 96%",
    "muted-foreground": "220 9% 46%",
    accent: "214 16% 96%",
    "accent-foreground": "222 20% 20%",
    destructive: "0 84% 60%",
    "destructive-foreground": "0 0% 100%",
    success: "160 84% 39%",
    "success-foreground": "0 0% 100%",
    warning: "38 92% 50%",
    "warning-foreground": "40 90% 8%",
    info: "217 91% 60%",
    "info-foreground": "0 0% 100%",
    border: "216 16% 90%",
    input: "216 16% 90%",
    ring: "246 85% 65%",
  },
  dark: {
    background: "222 22% 6%",
    foreground: "210 20% 96%",
    card: "222 20% 8%",
    "card-foreground": "210 20% 96%",
    popover: "222 22% 7%",
    "popover-foreground": "210 20% 96%",
    primary: "246 85% 65%",
    "primary-foreground": "222 40% 8%",
    secondary: "220 15% 14%",
    "secondary-foreground": "210 16% 90%",
    muted: "220 14% 13%",
    "muted-foreground": "218 11% 60%",
    accent: "220 15% 16%",
    "accent-foreground": "210 16% 92%",
    destructive: "0 72% 55%",
    "destructive-foreground": "0 0% 100%",
    success: "160 70% 45%",
    "success-foreground": "0 0% 100%",
    warning: "38 92% 55%",
    "warning-foreground": "40 90% 8%",
    info: "217 91% 66%",
    "info-foreground": "222 40% 8%",
    border: "220 14% 16%",
    input: "220 14% 18%",
    ring: "246 85% 65%",
  },
} as const;

export type ThemeMode = keyof typeof themeVars;
export type SemanticTone = keyof typeof semantic;
