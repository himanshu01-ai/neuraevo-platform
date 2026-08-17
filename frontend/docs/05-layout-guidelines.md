# 05 · Layout Guidelines

The app shell and the surfaces that compose every screen. Structure lives in
`layouts/`; screens fill the content region. Responsive rules in
[10 · Responsive](10-responsive-guidelines.md).

## The app shell

```
┌──────────────────────────────────────────────────────────────┐
│  Top Nav  (56px, glass, z-header)                             │
│  ◧ brand · breadcrumb/title      [ Search ⌘K ]   🔔  ☾  ⍟ ⌄  │
├───────────┬──────────────────────────────────────────────────┤
│           │                                                  │
│  Sidebar  │   Content region                                 │
│  (260/64) │   (container: content 1152 / wide 1440 / full)   │
│  z-sidebar│                                                   │
│           │   ┌─ Page header (title, description, actions) ─┐ │
│  nav      │   │                                             │ │
│  groups   │   ├─ Page body (cards / table / graph / panes) ┤ │
│           │   └─────────────────────────────────────────────┘ │
│  ─────    │                                                  │
│  account  │                                                  │
└───────────┴──────────────────────────────────────────────────┘
```

- **Persistent chrome:** Top Nav + Sidebar do not re-mount or re-animate on route
  change. Only the content region transitions ([03 · Motion](03-motion-guidelines.md)).
- **Content widths by screen type:** reading/forms → `prose` (672) or `content`;
  dashboards/tables → `wide` (1440); workspace/workflow canvas → `full`.

## Top Navigation

- 56px tall, `surface-glass`, hairline bottom border, `z-header`.
- **Left:** brand mark (links Home) + current page title / breadcrumb.
- **Center-left:** global **Search** — a ⌘K trigger styled as an input hint,
  not a live search box. Opens the Command Palette.
- **Right:** Notifications (bell + unread dot → panel), Theme toggle, Account menu.
- Never holds primary page actions — those live in the page header.

## Sidebar

- Persistent left rail, `z-sidebar`. **Expanded 260px** (icon + label) /
  **Collapsed 64px** (icon-only, tooltips). State persisted in `store/ui.store`.
- **Primary nav order** (mirrors `types/domain.ts` + navigation doc): Home,
  Workspace, Tasks, Workflow, Memory, Dashboard — then a **Capabilities** group:
  Files, Browser, Python, Email, Calendar, GitHub — then Settings pinned bottom.
- Active item: `primary` label, `accent` background, 2px leading indicator.
- Groups separated by `overline` section labels. Account/employee status sits at
  the bottom.

## Content layout

- Every screen opens with a **Page Header**: title (`h1`), one-line description,
  right-aligned primary/secondary actions. Below it, the page body on the 12-col
  grid with `section` vertical rhythm.
- Prefer **panels of cards** and **tables** over free-form layouts. Two- and
  three-pane layouts (list → detail → inspector) unlock at `xl`/`3xl`.

## Cards, panels, surfaces

- Card spec in [04 · Components](04-component-guidelines.md). Panels group related
  cards under a titled region. Keep to a max of ~3 elevation planes on screen:
  background → card → popover/modal.

## Dialogs & drawers

- **Dialog** for focused decisions/short forms (centered, `modal`).
- **Drawer/Sheet** for detail & inspectors that keep context (edge-anchored).
- **AlertDialog** for destructive confirmation. All trap focus and restore it.

## Command palette (⌘K)

- Global launcher at `z-commandPalette`, `popover` surface, opened from Top Nav
  search or ⌘K / Ctrl-K. Sections: **Navigate** (screens), **Delegate** (start a
  task), **Actions** (context commands), **Search** (entities). Full keyboard
  model; fuzzy match; recent + suggested at top. This is the primary fast path,
  echoing Raycast/Linear.

## Notifications

- Bell in Top Nav → dropdown panel of recent items (task completed, approval
  required, run failed), tone-coded, with deep links. Transient events also raise
  **toasts** (`z-toast`, auto-dismiss). Approval-required notifications are
  persistent until resolved.

## Search

- Two tiers: (1) **global** via the Command Palette (cross-entity, keyboard),
  (2) **local** scoped filters within tables/lists (inline input + facets). Never
  put a chat box where a search belongs.

## Mobile navigation (< md)

- Sidebar collapses into a **bottom tab bar** (Home, Workspace, Tasks, Workflow,
  More) + a slide-in **drawer** for the full nav and Capabilities. Top Nav shrinks
  to brand + search + account. Multi-pane layouts collapse to a single stacked
  column with drill-in navigation.

## Desktop & large screens

- **Desktop (xl, default target):** full shell, two-pane where useful.
- **Large / ultra-wide (3xl, 1920+):** Workspace and Workflow expand to
  **dual-pane + inspector** (graph/canvas + live timeline + detail). Content stays
  within `wide` unless the screen is a `full` canvas; never let line lengths or
  card grids stretch edge-to-edge unbounded.

## Layout rules

- One primary action per screen (in the page header). One question per screen
  ([00 · Overview](00-overview.md)).
- Respect the shell: features render **inside** the content region; they don't
  spawn their own global chrome.
- Density is deliberate but never cramped — honor `card`/`field`/`section`
  spacing roles.
