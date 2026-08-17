/**
 * NeuraEvo Design System — Border Tokens
 *
 * Hairline borders are the primary separation device in this system. Border
 * color is theme-aware via the `--border` CSS variable; these tokens define
 * width and style vocabulary.
 */

export const borderWidth = {
  0: "0px",
  hairline: "1px", // DEFAULT — dividers, cards, inputs
  thick: "1.5px", //  emphasized / active outlines
  focus: "2px", //    focus rings (paired with ring-offset)
} as const;

export const borderStyle = {
  solid: "solid",
  dashed: "dashed", // drop zones, placeholders, empty states
} as const;

export type BorderWidthToken = keyof typeof borderWidth;
