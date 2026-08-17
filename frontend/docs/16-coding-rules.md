# 16 · Frontend Coding Rules

The concrete engineering standard for writing frontend code. Complements the
principles in [08 · Developer Rules](08-developer-rules.md) and the boundaries in
[06 · Architecture](06-frontend-architecture.md) / [09 · State & API](09-state-and-api.md)
with day-to-day specifics. **Documentation only — no code shipped this sprint.**

## Naming conventions

- **Components:** `PascalCase` file + export, one component per file
  (`StatusBadge.tsx`). **Hooks:** `useThing.ts` / `useThing`. **Stores:**
  `thing.store.ts` exporting `useThingStore`. **Services:** `resource.ts`
  (`tasks.ts`). **Utils:** `verbNoun` functions in `kebab-or-camel.ts`.
- **Types/interfaces:** `PascalCase`; no `I`/`T` prefixes. **Enum-like** values:
  UPPERCASE string-literal unions mirroring the backend (`"RUNNING"`).
- **Booleans:** `is/has/should/can` prefix. **Handlers:** `handleX` (definition),
  `onX` (prop). **Constants:** `UPPER_SNAKE` for true module constants.
- **Files match their default/primary export.** No `index.tsx` god-barrels beyond
  a feature's public `index.ts`.

## Folder rules

- The 14 top-level folders are fixed — no new ones, no renames/moves
  ([06](06-frontend-architecture.md)). Put a file where its README says.
- Domain-specific UI → `features/<domain>/`; domain-agnostic → `components/`.
- Co-locate feature parts (`components/`, `hooks/`, `types.ts`) under the feature;
  expose only via the feature `index.ts`.
- No `fetch` outside `services/`; no design values outside `design-system`/Tailwind.

## Component architecture

- **Server Components by default.** Add `"use client"` only at interactive leaves
  (state/effects/handlers/Framer Motion/R3F/Zustand/forms); keep it as low in the
  tree as possible.
- Small and focused; extract when a component does two jobs. Presentational vs.
  container split — data hooks feed presentational children via props.
- Variants via **CVA**; combine classes with `cn()`. Accept `className`, forward
  refs, spread valid DOM props. No inline style objects for themeable values.
- Derive, don't duplicate, state; lift state only as far as needed. No business
  logic in `app/` route files (compose features there).

## Hooks rules

- Rules of Hooks strictly (top level, stable order). Prefix `use`.
- Cross-cutting hooks → `hooks/`; feature data hooks → `features/*/hooks/` wrapping
  TanStack Query. Hooks never call `fetch` directly — go through `services/`.
- Complete, typed dependency arrays; memoize (`useMemo`/`useCallback`) only for
  measured cost or referential-stability needs, not reflexively.
- One responsibility per hook; return a typed object/tuple, not a grab-bag.

## Services rules

- The **only** backend caller ([09](09-state-and-api.md)). No React imports here.
- One module per resource; every function is typed and returns validated data
  (Zod at the boundary). All failures normalized to `ApiError`.
- No raw URLs (use `lib/env`); no secrets/tokens in query strings; auth via the
  `http.ts` interceptor. Query keys come from the central `query-keys` factory.

## Zustand rules

- **UI/client state only** — never a cache for server data. One slice per concern;
  compose, no god-store.
- Select narrowly (`useStore(s => s.x)`) to avoid needless re-renders; keep
  actions in the store, not scattered in components. Persist only durable UI prefs
  (theme, sidebar) via `persist`; never persist server data.

## TanStack Query rules

- All server reads/writes via Query hooks in `features/*/hooks/`. Keys from the
  factory; mutations invalidate the narrowest relevant prefix.
- Set sensible `staleTime`/`retry` per resource; live data uses polling/streaming
  hidden behind the feature hook. Prefer optimistic updates with rollback.
- Render the three states from shared primitives: **loading** (skeleton),
  **empty** (EmptyState), **error** (ErrorState with Retry from `ApiError`).

## TypeScript rules

- `strict` + `noUncheckedIndexedAccess` on. **No `any`** (use `unknown` + narrow);
  no non-null `!` except with a proven invariant + comment.
- Prefer `type`; `interface` for extendable public shapes. Discriminated unions for
  variant/state modeling. `as const` for literal tables.
- `import type` for type-only imports (isolatedModules). Domain vocabulary comes
  from `types/domain.ts` — don't redefine status/enum literals.
- Type at boundaries (props, service returns, store shape); let inference handle
  the rest. No `@ts-ignore` without a justifying comment.

## Tailwind rules

- **Tokens only:** semantic utilities mapped to CSS variables (`bg-background`,
  `text-muted-foreground`, `border-border`, `shadow-md`, `rounded-md`, `z-header`).
- **No hardcoded/arbitrary values** for themeable properties — no `bg-[#6C5CF2]`,
  no `p-[13px]`, no off-scale sizes. Missing value → add a token.
- Conditional classes via `cn()` (never string concatenation); class order via
  `prettier-plugin-tailwindcss`. No per-component `.css` files.
- Style light **and** dark; verify both. Reduced-motion is global — don't re-disable.

## Accessibility checklist (per component/screen)

- [ ] Keyboard-complete; logical tab order; `Esc` closes overlays.
- [ ] Visible `:focus-visible`; overlays trap + restore focus.
- [ ] Native elements/Radix primitives; correct roles; icon-only controls labeled.
- [ ] AA contrast in light **and** dark; status never color-only.
- [ ] Forms labeled; errors `aria-invalid` + `aria-describedby` + announced.
- [ ] Targets ≥ 24px (40px mobile); usable at 320px and 200% zoom.
      Full list: [07 · Accessibility](07-accessibility-guidelines.md).

## Responsive checklist

- [ ] Mobile-first; complexity layered with `min-width` utilities.
- [ ] Verified at 375 / 768 / 1280 / 1920 (+ 320 & 200% zoom).
- [ ] Sidebar → bottom tabs/drawer < md; multi-pane → stacked drill-in on mobile.
- [ ] No page horizontal scroll (only inside scrollable regions).
      Full rules: [10 · Responsive](10-responsive-guidelines.md).

## Animation rules

- Durations/easings from `design-system/tokens/motion.ts`; UI motion ≤ 320ms.
- Animate the element that changed, not the screen; never block input.
- Respect `prefers-reduced-motion` (global + `MotionProvider`/`useReducedMotion`).
  Full rules: [03 · Motion](03-motion-guidelines.md).

## Performance rules

- Server-render by default; minimize client bundle; `next/dynamic` for heavy/3D.
- Per-icon Lucide imports; `optimizePackageImports` for `lucide-react`/
  `framer-motion`; no `import * as`.
- `next/image` (AVIF/WebP, sized); memoize expensive renders; virtualize long
  lists/tables. Skeletons + optimistic UI for perceived speed. Avoid layout shift.
- Budget 3D (draw calls, offscreen pause, static fallback) — [14](14-illustration-guidelines.md).

## Import conventions

- Alias imports only (`@/components/...`), never deep relative `../../../`.
- Order: React/Next → external libs → `@/` internal → relative → styles/types
  (enforced by lint/format). `import type` for types.
- No circular imports; no cross-feature imports; no importing up the layer stack.

## File organization

- One primary export per file; co-locate tightly-related pieces; feature-public
  surface via `index.ts`. Keep files focused (~a screenful of logic); split when a
  file mixes concerns. Tests co-located as `*.test.ts(x)` when added.

## Code review rules

- PRs are small and single-purpose; description states scope + the one question
  the change serves. CI green (`typecheck`, `lint`, `format`) before review.
- Reviewer verifies against the [08 · Developer Rules](08-developer-rules.md)
  definition of done and the [17 · Design Review Checklist](17-design-review-checklist.md):
  tokens-only, layer boundaries, a11y, responsive, dark mode, no hardcoded values,
  backend-vocabulary compatibility.
- Additive-only; no drive-by refactors of frozen foundation without explicit
  agreement. Flag any missing spec instead of improvising a one-off.
