# 13 · Icon System

How NeuraEvo uses icons. Icons are functional wayfinding and status signals, not
decoration. This doc is the single reference; it aligns with the icon rules in
[02 · Brand](02-brand-guidelines.md) and [04 · Components](04-component-guidelines.md).

## Philosophy

- **Enterprise-quiet.** Icons clarify meaning and speed scanning; they never
  ornament. One icon per action or status — never a row of decorative glyphs.
- **Consistent geometry.** A single library, a single stroke weight, a fixed size
  set. Icons read as one family across the whole product.
- **Meaning is paired, never carried alone.** An icon that conveys state always
  sits with a text label or accessible name (colorblind + screen-reader safe).

## Library — Lucide React (only)

- **`lucide-react` is the only icon library.** No Font Awesome, Heroicons,
  Material Icons, Remix, custom SVG icon sets, or emoji in product chrome.
- Import per-icon (tree-shaken; `optimizePackageImports` is enabled in
  `next.config.mjs`): `import { Workflow, CheckCircle2 } from "lucide-react";`
- Brand marks (`assets/brand/*`) are **not** icons and live outside this system.
- If a needed glyph is missing from Lucide, request a design-system addition
  (a matching-stroke custom SVG in `components/brand` or `components/ui/icons`) —
  do not import a second library. See [08 · Developer Rules](08-developer-rules.md).

## Sizes

One size set, aligned to the 4px grid. `size` is the pixel square (Lucide `size`
prop / `w-* h-*`):

| px | Token use | Where |
| -- | --------- | ----- |
| 12 | `icon-xs` | dense inline meta, table cell adornment, tag |
| 14 | `icon-sm` | inline with 13–14px text, secondary buttons |
| 16 | `icon-md` | **default in-text / button icon** |
| 18 | `icon-lg` | comfortable buttons, list rows |
| 20 | `icon-nav` | **navigation + top-nav default** |
| 24 | `icon-xl` | section headers, emphasis, mobile targets |
| 32 | `icon-2xl` | empty-state secondary, feature tiles |
| 48 | `icon-3xl` | empty-state hero, onboarding |

Rules: never scale an icon to an off-scale size; match icon size to adjacent text
(16px icon with 14–16px text, 20px with nav). Optical alignment beats exact
baseline — nudge with `translate` only when clearly misaligned.

## Stroke

- **1.5px stroke, always.** Set globally via Lucide `strokeWidth={1.5}` (wrap in a
  shared `<Icon>` default so it is never re-specified ad hoc). Matches the rounded
  geometry of the brand mark.
- **Rounded** line caps and joins (Lucide default). Do not switch to square caps.
- Do not thicken/thin stroke to imply weight — use size or color for emphasis.
- Icons are line-style (outline). No filled/duotone variants except a status dot,
  which is a shape, not an icon.

## Semantic colors (tokens only)

Icons inherit `currentColor`. Color is applied via Tailwind text utilities that
map to design tokens — **never a hardcoded hex**.

| Intent | Utility (token) | Use |
| ------ | --------------- | --- |
| Default | `text-muted-foreground` | resting/secondary icons |
| Emphasis | `text-foreground` | active/high-attention neutral |
| Brand / active | `text-primary` | selected nav, primary action, AI |
| Success | `text-success` | COMPLETED · APPROVED · HEALTHY |
| Info / running | `text-info` | RUNNING · QUEUED |
| Warning | `text-warning` | PAUSED · PENDING (approval) · DEGRADED |
| Danger | `text-destructive` | FAILED · REJECTED · UNHEALTHY |
| Disabled | inherits + `opacity-40` | disabled controls |

Status color is resolved through `types/domain.ts` (`status → tone → color`) — the
same mapping used by the StatusBadge — so icons and badges never disagree.

## Navigation icon mapping

Sidebar / command-palette icons (from the nav registry, [12 · Navigation](12-navigation-architecture.md)), rendered at 20px:

| Destination | Lucide icon |
| ----------- | ----------- |
| Home | `Home` |
| Workspace | `Bot` (accent: `Sparkles`) |
| Tasks | `ListChecks` |
| Workflow | `Workflow` (alt `Network`) |
| Memory | `Brain` |
| Dashboard | `Gauge` (alt `Activity`) |
| **Capabilities** | |
| Files | `Folder` |
| Browser | `Globe` |
| Python | `SquareTerminal` |
| Email | `Mail` |
| Calendar | `Calendar` |
| GitHub | `Github` |
| Settings | `Settings` |

Capability icons derive from `CAPABILITIES` in `types/domain.ts`, so navigation
and capability screens use the identical glyph everywhere.

## Workflow / status icon mapping

Lifecycle (`LifecycleStatus`) and node (`NodeStatus`):

| Status | Icon | Tone |
| ------ | ---- | ---- |
| PENDING | `Circle` | neutral |
| QUEUED | `Clock` | info |
| RUNNING | `LoaderCircle` (spin, reduced-motion → static) | info |
| PAUSED | `PauseCircle` | warning |
| COMPLETED | `CheckCircle2` | success |
| FAILED | `XCircle` | danger |
| CANCELLED | `CircleSlash` | neutral |
| SKIPPED | `MinusCircle` | neutral |

Approvals (`ApprovalStatus`): PENDING `Clock` (warning) · APPROVED `CheckCircle2`
(success) · REJECTED `XCircle` (danger).

Health (`HealthState`): HEALTHY `ShieldCheck` (success) · DEGRADED `AlertTriangle`
(warning) · UNHEALTHY `ShieldAlert` (danger) · UNKNOWN `HelpCircle` (neutral).

These maps are the canonical status iconography; define them once alongside the
`types/domain.ts` tone maps and reuse — no per-component `if status ===` glyphs.

## Interaction states

- **Rest:** `text-muted-foreground` (or contextual token).
- **Hover:** transition to `text-foreground` / `text-primary` over `fast` (120ms);
  icon-only buttons also tint background `accent`.
- **Active/selected:** `text-primary`.
- **Focus:** the parent control shows the global `:focus-visible` ring — the icon
  itself gets no separate outline.
- **Disabled:** `opacity-40`, `pointer-events-none`.
- **Loading:** `LoaderCircle` with `animate-spin`; under `prefers-reduced-motion`
  it renders static (global rule) — pair with an accessible "Loading" label.

## Accessibility

- **Decorative icons** (next to a text label): `aria-hidden="true"` and no title.
- **Meaningful standalone icons** (icon-only button/status): provide an accessible
  name — `aria-label` on the control, or visually-hidden text. Never rely on the
  icon shape alone.
- Status icons must be paired with a label or `aria-label` mirroring the status
  (e.g., `aria-label="Failed"`), so meaning survives without color.
- Minimum interactive target 24×24px (40px on mobile) even if the glyph is 16px —
  pad the hit area. See [07 · Accessibility](07-accessibility-guidelines.md).

## Developer rules

- **Single source:** `lucide-react` only; no mixed icon libraries; no emoji as UI.
- **Wrap defaults:** a shared `<Icon>`/base sets `strokeWidth={1.5}` and default
  size so they are never re-specified inline.
- **Tokens only:** color via `text-*` token utilities; never a hardcoded hex or
  arbitrary value.
- **On-scale sizes only:** pick from {12,14,16,18,20,24,32,48}.
- **Status glyphs come from the canonical map**, not local conditionals.
- **Import per-icon** (tree-shakeable); never `import * as Icons`.
- One icon per action/status; if it doesn't add meaning, remove it.
