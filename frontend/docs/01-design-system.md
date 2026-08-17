# 01 · Design System

The design language, expressed as tokens. Source of truth:
`design-system/tokens/*` (TypeScript) mirrored to `styles/globals.css` (runtime
CSS variables) and mapped through `tailwind.config.ts` (utilities).

## Theming model

- **CSS variables are the runtime source of truth for color.** `:root` holds the
  light theme; `.dark` on `<html>` flips the whole app. Colors are stored as
  space-separated HSL triplets and consumed as `hsl(var(--token))`.
- **TS tokens are the design reference** and the only color source for non-CSS
  contexts (Framer Motion, Canvas, React Three Fiber, generated charts).
- **Sync rule:** a themed color change means editing **both** `themeVars` in
  `tokens/color.ts` **and** the matching variable in `globals.css`. Non-color
  scales (spacing, radius, motion, z-index) live only in tokens and flow through
  Tailwind.

## Color

### Palette

- **Neutral** — a cool near-neutral ramp (`neutral.0 … neutral.1000`). The
  structural backbone: backgrounds, surfaces, borders, text.
- **Brand — NeuraEvo Violet** (`brand.500 = #6C5CF2`). One confident accent.
  Used for primary actions, focus, active nav, the AI Core, and selected state.
  Never used as a large fill behind body text.
- **Semantic** — `success` (emerald), `warning` (amber), `danger` (red),
  `info` (blue), `neutral` (gray). Each has `soft` / `base` / `strong` / `fg`.

### The shadcn variable contract

| Token | Role |
| ----- | ---- |
| `--background` / `--foreground` | app canvas + default text |
| `--card` / `--card-foreground` | raised surfaces |
| `--popover` / `--popover-foreground` | menus, dropdowns, ⌘K |
| `--primary` / `--primary-foreground` | brand actions |
| `--secondary` / `--muted` / `--accent` | quiet fills + subdued text |
| `--destructive` | irreversible / danger |
| `--success` `--warning` `--info` | status surfaces |
| `--border` / `--input` / `--ring` | hairlines + focus |
| `--radius` | base corner radius (0.75rem) |

### Status → tone → color

Status is never colored ad hoc. `types/domain.ts` maps every backend status to a
`StatusTone`, and tone maps to a semantic color:

```
COMPLETED / APPROVED / HEALTHY   → success  (emerald)
RUNNING / QUEUED / INFO          → info     (blue)
PAUSED / PENDING(approval)/DEGRADED → warning (amber)
FAILED / REJECTED / UNHEALTHY    → danger   (red)
CANCELLED / IDLE / DISABLED      → neutral  (gray)
```

### Color usage rules

- Meaning is never carried by color alone — always pair with an icon/label
  (accessibility + colorblind safety).
- Body text on any surface must meet **AA 4.5:1**; large text and UI glyphs
  **3:1**. See [07 · Accessibility](07-accessibility-guidelines.md).
- Brand violet is an accent, not a background. Max ~10% of any viewport.

## Typography

- **Families:** `--font-sans` (Inter / geometric-humanist) for UI; `--font-mono`
  (JetBrains Mono) for code, IDs, metrics, workflow node internals.
- **Baseline is 14px** (`text-base`) — an enterprise density choice, not 16px.
  16px (`text-md`) is reserved for comfortable prose.
- **Scale** — 1.20 minor-third: 12 · 13 · 14 · 16 · 18 · 22 · 28 · 36 · 48 · 60.
- **Weights** — 400 / 500 / 600 / 700. Headings use 600; 700 is display-only.
- **Named roles** (`textStyle` in `tokens/typography.ts`): `display`, `h1–h3`,
  `body`, `bodyStrong`, `caption`, `overline`, `code`. Reference roles, not sizes.
- **Tracking** — tighten headings (`-0.01em`), tighten display (`-0.02em`),
  widen overline/eyebrow labels (`0.08em`, uppercase).

## Spacing

- **4px base grid.** Every margin/padding/gap is a scale step — no arbitrary px.
- Semantic roles (`spacingRole`): `card` (24), `field` (16), `section` (48),
  `gutter` (32 desktop / 16 mobile), `inline` (8).
- Vertical rhythm: sections separated by `section`; related groups by `field`.

## Radius

`none · xs 4 · sm 8 · md 12 (default) · lg 16 · xl 24 · full`. Buttons/inputs/
cards use `md`; dialogs/panels `lg`; hero surfaces `xl`; avatars/dots/pills `full`.

## Elevation & borders

- **Hairline-first.** Separate surfaces with a 1px `--border` before reaching for
  shadow. Shadows are low-spread (`xs … xl`); `glow` is brand-only (AI Core,
  focus emphasis).
- In **dark mode**, elevation is expressed by surface lightness
  (`card` lighter than `background`), not heavy shadow.
- Border widths: `hairline 1px` (default), `thick 1.5px` (active), `focus 2px`.

## Grid & breakpoints

- Mobile-first. Breakpoints align to Tailwind: `sm 640 · md 768 · lg 1024 ·
  xl 1280 · 2xl 1536 · 3xl 1920`.
- 12-column app grid, 24px gutter. Content containers: `prose 672 · content 1152
  · wide 1440 · full`. Details in [10 · Responsive](10-responsive-guidelines.md).

## Z-index

One ordered contract (`tokens/zIndex.ts`): `sidebar 100 · header 200 · dropdown
1000 · sticky 1100 · overlay 1200 · modal 1300 · popover 1400 · commandPalette
1500 · toast 1600 · tooltip 1700`. Never invent an ad-hoc z-index.

## Naming conventions

- **Tokens:** `category.scaleOrRole` (`brand.500`, `spacingRole.card`,
  `motion.transition.enter`).
- **CSS variables:** kebab-case, shadcn contract (`--muted-foreground`).
- **Tailwind:** semantic utility names (`bg-background`, `text-muted-foreground`,
  `border-border`, `shadow-md`, `rounded-md`, `z-header`).
- **Components:** PascalCase files/exports; **hooks** `useThing`; **stores**
  `thing.store.ts`; **services** `resource.ts`; **types** PascalCase, enums
  UPPERCASE string literals (mirroring backend).
- **Do not** introduce a color/size/duration outside the token system. If a value
  is missing, add a token — don't inline a literal.
