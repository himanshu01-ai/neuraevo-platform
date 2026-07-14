/**
 * NeuraEvo Design System — Typography Tokens
 *
 * Two families only: a geometric-humanist sans for UI, and a mono for code,
 * IDs, metrics and workflow node internals. Loaded via `next/font` in the
 * root layout and exposed as CSS variables `--font-sans` / `--font-mono`.
 */

export const fontFamily = {
  sans: "var(--font-sans), Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif",
  mono: "var(--font-mono), 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace",
} as const;

/** Type scale — a 1.20 (minor-third) ratio, tuned for dense enterprise UI. */
export const fontSize = {
  xs: "0.75rem", //   12px — captions, meta, table dense
  sm: "0.8125rem", // 13px — secondary UI text
  base: "0.875rem", //14px — DEFAULT body / UI (enterprise baseline, not 16)
  md: "1rem", //      16px — comfortable body / prose
  lg: "1.125rem", //  18px — lead text, card titles
  xl: "1.375rem", //  22px — section headings
  "2xl": "1.75rem", //28px — page titles
  "3xl": "2.25rem", //36px — hero secondary
  "4xl": "3rem", //   48px — hero primary
  "5xl": "3.75rem", //60px — marketing display
} as const;

export const fontWeight = {
  normal: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
} as const;

export const lineHeight = {
  none: 1,
  tight: 1.15,
  snug: 1.3,
  normal: 1.5,
  relaxed: 1.65,
} as const;

export const letterSpacing = {
  tighter: "-0.02em", // display / hero
  tight: "-0.01em", //   headings
  normal: "0em",
  wide: "0.02em",
  wider: "0.08em", //    overline / eyebrow labels (uppercase)
} as const;

/**
 * Named text roles — the vocabulary product code should reference instead of
 * raw sizes. Documented in docs/01-design-system.md.
 */
export const textStyle = {
  display: { size: fontSize["4xl"], weight: fontWeight.bold, leading: lineHeight.tight, tracking: letterSpacing.tighter },
  h1: { size: fontSize["2xl"], weight: fontWeight.semibold, leading: lineHeight.snug, tracking: letterSpacing.tight },
  h2: { size: fontSize.xl, weight: fontWeight.semibold, leading: lineHeight.snug, tracking: letterSpacing.tight },
  h3: { size: fontSize.lg, weight: fontWeight.semibold, leading: lineHeight.snug, tracking: letterSpacing.normal },
  body: { size: fontSize.base, weight: fontWeight.normal, leading: lineHeight.normal, tracking: letterSpacing.normal },
  bodyStrong: { size: fontSize.base, weight: fontWeight.medium, leading: lineHeight.normal, tracking: letterSpacing.normal },
  caption: { size: fontSize.xs, weight: fontWeight.normal, leading: lineHeight.snug, tracking: letterSpacing.normal },
  overline: { size: fontSize.xs, weight: fontWeight.semibold, leading: lineHeight.none, tracking: letterSpacing.wider },
  code: { size: fontSize.sm, weight: fontWeight.normal, leading: lineHeight.normal, tracking: letterSpacing.normal },
} as const;

export type TextRole = keyof typeof textStyle;
