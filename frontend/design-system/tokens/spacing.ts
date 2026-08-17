/**
 * NeuraEvo Design System — Spacing Tokens
 *
 * A strict 4px base grid. Every margin, padding, and gap resolves to one of
 * these steps — never an arbitrary pixel value. Tailwind's default spacing
 * scale is 4px-based and aligned to this; the named steps below document the
 * canonical rhythm for layout code and specs.
 */

export const space = {
  0: "0px",
  px: "1px",
  0.5: "2px",
  1: "4px",
  1.5: "6px",
  2: "8px",
  2.5: "10px",
  3: "12px",
  4: "16px",
  5: "20px",
  6: "24px",
  8: "32px",
  10: "40px",
  12: "48px",
  16: "64px",
  20: "80px",
  24: "96px",
  32: "128px",
} as const;

/** Semantic spacing roles for consistent component and layout construction. */
export const spacingRole = {
  /** Gap between tightly-related inline items (icon + label). */
  inlineTight: space[1.5],
  /** Default inline gap (button content, badge). */
  inline: space[2],
  /** Padding inside compact controls (inputs, sm buttons). */
  controlPadY: space[2],
  controlPadX: space[3],
  /** Padding inside cards / panels. */
  card: space[6],
  /** Gap between stacked form fields. */
  field: space[4],
  /** Gap between page sections. */
  section: space[12],
  /** App gutter (page horizontal padding at desktop). */
  gutter: space[8],
  /** App gutter at mobile. */
  gutterMobile: space[4],
} as const;
