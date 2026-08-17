# 10 · Responsive Guidelines

Mobile-first, breakpoint-driven, token-aligned. Values match Tailwind screens and
`design-system/tokens/breakpoint.ts` so utilities and JS never disagree.

## Breakpoints

| Token | Min width | Primary shift |
| ----- | --------- | ------------- |
| (base) | 0 | single column, bottom tab bar |
| `sm` | 640 | roomier phone / small tablet |
| `md` | 768 | **sidebar becomes persistent**; multi-column cards |
| `lg` | 1024 | full app shell; two-pane where useful |
| `xl` | 1280 | **default design target**; list→detail panes |
| `2xl` | 1536 | wider content, more table columns |
| `3xl` | 1920 | **dual-pane + inspector** (Workspace/Workflow) |

## Layout adaptation by tier

**< md (mobile)**

- Sidebar → **bottom tab bar** (Home, Workspace, Tasks, Workflow, More) +
  slide-in drawer for full nav/Capabilities.
- Top Nav shrinks to brand + search + account.
- Multi-pane screens collapse to one stacked column with **drill-in** navigation
  (list → push detail). Tables → stacked cards or horizontal scroll with a sticky
  first column.
- Workflow graph → vertical step list; the 3D AI Core → static/simplified frame.

**md–lg (tablet)**

- Persistent collapsible sidebar (default collapsed on `md`). Two-column card
  grids. Dialogs remain modal; drawers full-height.

**xl (desktop, target)**

- Full shell; list→detail two-pane on Tasks/Memory/Workflow. Content within
  `content`/`wide` containers.

**3xl (ultra-wide)**

- Workspace & Workflow expand to **three regions**: graph/canvas · live timeline ·
  detail inspector. Cap content width (`wide` 1440) except true `full` canvases;
  never stretch card grids or text edge-to-edge.

## Rules

- **Design mobile-first**, layer complexity upward with `min-width` utilities.
- Fluid within a tier (grid/flex, `%`/`fr`, `clamp()` for hero type); switch
  structure at breakpoints, not pixel-peeping.
- Touch targets ≥ 40px on mobile controls; hover-only affordances must have a
  tap/focus equivalent.
- Test the canonical set: **375** (mobile), **768** (tablet), **1280** (desktop),
  **1920** (ultra-wide) — plus 320px and 200% zoom for a11y
  ([07](07-accessibility-guidelines.md)).
- No horizontal page scroll except inside explicitly scrollable regions (wide
  tables, the workflow canvas).
- Images/media: `max-width:100%`, responsive `next/image` sizes; the AI Core
  scales down (and simplifies) on small/low-power devices.
