# 04 · Component Guidelines

Design specifications for the component library. **Specs only — no business
implementation in Sprint 17.0.** Primitives are generated from shadcn/ui into
`components/ui/`, themed via tokens; composed patterns live in
`components/patterns/`. Every component consumes theme through Tailwind utilities
(`bg-*`, `text-*`, `border-*`) and the `cn()` helper — never hardcoded values.

Shared contract for all interactive components:

- Accept `className`, forward refs, spread valid DOM props.
- Variants via **CVA** (`class-variance-authority`); no conditional class soup.
- Keyboard operable, visible `:focus-visible` ring, correct ARIA role/label.
- Sizes align to the 4px grid; radius from the radius scale; motion from tokens.

---

## Buttons

- **Variants:** `primary` (violet, primary-fg), `secondary` (muted fill),
  `outline` (hairline border), `ghost` (transparent, hover `accent`), `link`,
  `destructive` (red).
- **Sizes:** `sm` (h-8 / 32), `md` (h-9 / 36, default), `lg` (h-10 / 40),
  `icon` (square). Radius `md`. Gap `inline` between icon + label; icons 16–18px.
- **States:** hover tint 120ms · press scale 0.98 · `disabled` opacity 0.4 +
  `pointer-events-none` · `loading` shows a leading spinner and disables.
- One primary action per view/section. Destructive actions require confirmation.

## Inputs (Input, Textarea, Select, Combobox, Checkbox, Radio, Switch)

- Height h-9 (36), radius `sm`, `--input` border, `bg-background`, 14px text,
  `muted-foreground` placeholder. Focus: 2px `ring` + offset.
- **States:** default · focus · filled · `disabled` · `error` (danger border +
  message) · `readonly`.
- Always pair with a `<Label>` (or `aria-label`). Errors render below via
  RHF + Zod; the field gets `aria-invalid` and `aria-describedby`.
- Select/Combobox render in a `popover`-layer menu with keyboard nav and type-ahead.

## Cards

- `bg-card`, hairline border, radius `lg`, padding `card` (24). Shadow `sm` at
  rest, `md` on hover only if interactive. Slots: header (title + optional
  action), body, footer.
- Variants: `default`, `interactive` (hover lift + cursor), `muted` (quiet inset),
  `accent` (brand hairline + faint glow, for AI/highlight surfaces).

## Badges & Status Badge

- **Badge:** pill (`radius full`), 12px, `overline` weight; tones map to semantic
  soft-bg + strong-fg.
- **StatusBadge** (pattern): input is a backend status; it resolves
  status→tone→color via `types/domain.ts` maps and renders **dot + label**
  (never color-only). A `RUNNING` badge shows a soft `pulse-glow` dot.
  One component covers lifecycle, approval, node, and health statuses.

## Progress

- **Linear:** 4px track (`muted`), `primary` fill, eased width. Determinate by
  default; indeterminate uses a traveling segment.
- **Ring:** for task/workflow completion; stroke eases, success flips to a
  `success` check with one `emphasized` tick.
- **Steps:** numbered stepper for Task → Planning → Execution → Approval → Result.

## Tables (DataTable)

- Dense rows (h-10 / 40), hairline row dividers, sticky header (`raised` z),
  `muted-foreground` column labels (`overline`). Row hover = `accent` tint.
- Features spec'd: sort, column visibility, row selection, pagination, sticky
  first column, right-aligned numerics in `--font-mono`. Empty → EmptyState;
  loading → skeleton rows. No zebra striping (borders carry separation).

## Sidebar (see [05 · Layout](05-layout-guidelines.md))

- Persistent rail, `z-sidebar`. Expanded 260px / collapsed 64px (icon-only).
  Items: icon + label, active item = `primary` text + subtle `accent` bg +
  2px leading indicator. Sections grouped with `overline` headers. Tooltip labels
  when collapsed.

## Navbar / Top Nav

- Height 56px, `surface-glass`, hairline bottom border, `z-header`. Left: brand +
  breadcrumbs/page title. Center/left: global Search (⌘K trigger). Right:
  notifications bell (unread dot), theme toggle, account menu.

## Dialogs, Drawers, Sheets

- Scrim `overlay` (opacity 0.6) + `modal` content. Dialog: centered, radius `lg`,
  shadow `xl`, max-w by role. Drawer/Sheet: edge-anchored for detail/inspector.
- Focus trapped; `Esc` + scrim click close; focus returns to trigger. Title +
  description required (`aria-labelledby`/`aria-describedby`). Destructive
  confirmations use an AlertDialog (no scrim-dismiss).

## Dropdowns & Menus

- `popover` layer, radius `md`, shadow `lg`, 4px item padding, keyboard nav,
  optional icons/shortcuts/`Separator`/checkbox items. Right-click context menus
  share the style.

## Tabs

- Underline style (2px `primary` indicator, animated `base`), `muted-foreground`
  inactive. Roving-tabindex keyboard model; panels linked via `aria-controls`.
  Use for in-page section switching, never for primary navigation.

## Workflow Node (pattern)

- The unit of the workflow graph. Card-like: `bg-card`, radius `md`, hairline
  border tinted by node status tone; header = capability icon + node name;
  body = current step / short status; footer = duration + optional artifact chip.
- States: `PENDING` (muted), `RUNNING` (info + ring pulse), `COMPLETED`
  (success), `FAILED` (danger + retry affordance), `SKIPPED` (dashed, dim).
- Handles/ports on left (in) and right (out); selected node gets `ring` + glow.
  Detailed graph spec in [11 · Screen Architecture](11-screen-architecture.md).

## Timeline

- Vertical list of events (planning, execution, approvals, artifacts). Each row:
  tone dot + connector line, timestamp (`--font-mono`, `muted-foreground`),
  title, optional expandable detail. Used in Workspace and Task detail.

## Loading Skeleton

- `muted` blocks with `shimmer`, matching the final content's shape and size
  (avoid layout shift). Never a full-screen spinner for content; skeleton the
  regions independently.

## Empty State

- Centered: line illustration/icon, one-line title, supporting sentence, one
  primary action (e.g., "Delegate a task"). Calm, never an error tone. Every list
  and screen defines its empty state.

## Error State

- Inline (form field / section) or block (failed load). Block: `danger` icon,
  plain-language cause, a **Retry** action, optional details disclosure.
  Never a raw stack trace. App-level failures use `app/error.tsx` with the same
  pattern. Distinguish _empty_ (no data yet) from _error_ (something broke).

## Success State

- Quiet confirmation: inline `success` badge/toast + a single `emphasized` tick.
  For completed work, surface the **artifact/result**, not a celebration.

---

### Component definition of done

Themed via tokens · all states covered (default/hover/focus/active/disabled/
loading/error/empty) · keyboard + screen-reader accessible · responsive · motion
from tokens + reduced-motion safe · no hardcoded color/size/duration · documented
props. Full checklist in [08 · Developer Rules](08-developer-rules.md).
