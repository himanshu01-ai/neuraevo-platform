/**
 * NeuraEvo Design System — Z-Index Scale
 *
 * A single, ordered stacking contract. Never invent an ad-hoc z-index in a
 * component; reference a named layer so overlays compose predictably.
 */

export const zIndex = {
  base: 0,
  raised: 10, //       hover-lifted cards, sticky table headers
  sidebar: 100, //     app sidebar / rail
  header: 200, //      top navigation bar
  dropdown: 1000, //   menus, selects, comboboxes
  sticky: 1100, //     sticky action bars
  overlay: 1200, //    dialog / drawer scrim
  modal: 1300, //      dialogs, drawers, sheets
  popover: 1400, //    popovers, tooltips over modals
  commandPalette: 1500, // ⌘K launcher — above everything structural
  toast: 1600, //      notifications
  tooltip: 1700, //    top-most transient hint
} as const;

export type ZLayer = keyof typeof zIndex;
