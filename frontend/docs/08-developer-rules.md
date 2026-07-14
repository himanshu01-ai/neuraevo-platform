# 08 · Developer Rules

The operating contract for every frontend sprint after 17.0. These rules protect
the design system and architecture the way the backend's rules protect its
layers.

## Golden rules

1. **Tokens or nothing.** No hardcoded color/spacing/radius/shadow/duration.
   Missing value → add a token, don't inline a literal.
2. **Respect the layers.** Imports flow downward only ([06](06-frontend-architecture.md)).
   No cross-feature imports. No `fetch` outside `services/`.
3. **Server-first.** Default to Server Components; `"use client"` only at
   interactive leaves.
4. **Separate state.** Server data → TanStack Query. UI state → Zustand. Never mix
   ([09](09-state-and-api.md)).
5. **Accessible by construction.** Meet [07](07-accessibility-guidelines.md) before
   calling anything done.
6. **Reuse primitives.** Compose `components/` before building new UI; prefer
   shadcn/Radix over hand-rolled overlays.
7. **Additive only.** No new top-level folders; no renaming/moving the 14 defined
   folders; extend, don't restructure.
8. **Don't touch the backend.** It is frozen. Adapt the frontend to its contracts.
9. **Mirror, don't invent, domain vocabulary.** Status/enum values come from
   `types/domain.ts` (which mirrors the backend), UPPERCASE, with `*_LABEL` maps
   for display.
10. **One question, one primary action per screen.**

## Component definition of done

- [ ] Themed only via tokens/Tailwind utilities (`cn()`); zero hardcoded values.
- [ ] Variants via CVA; accepts `className`; forwards refs; spreads DOM props.
- [ ] All states: default · hover · focus-visible · active · disabled · loading ·
      error · empty.
- [ ] Keyboard operable; correct roles/labels; focus trap/restore for overlays.
- [ ] AA contrast in **light and dark**.
- [ ] Motion from tokens; reduced-motion safe.
- [ ] Responsive from `sm`→`3xl`; usable at 320px and 200% zoom.
- [ ] No cross-layer/cross-feature imports; alias imports (`@/…`).
- [ ] `npm run typecheck` and `npm run lint` clean.

## Screen definition of done

Answers its one question in the first viewport · page header (title + one action)
· loading (skeleton), empty, and error states · registered in Sidebar + Command
Palette · deep-linkable route · responsive collapse to mobile · a11y pass on the
primary flow.

## Naming & conventions

- Components `PascalCase.tsx`; hooks `useThing.ts`; stores `thing.store.ts`;
  services `resource.ts`; types `PascalCase`, enum literals UPPERCASE.
- Named exports preferred; one component per file; co-locate feature parts under
  `features/<domain>/`.
- Tailwind class order via `prettier-plugin-tailwindcss`; conditional classes via
  `cn()`.

## Definition of "not this sprint" (17.0 boundaries)

Do **not**, in Sprint 17.0: build product pages, wire endpoints, add auth,
implement business components, create real workflows/dashboards, or install a live
app. Deliver tokens, structure, specs, and docs only.

## Quality gates (future sprints)

`typecheck` (tsc `--noEmit`, strict) · `lint` (next/core-web-vitals) · `format`
(prettier) · no broken imports · Lighthouse a11y ≥ 95 on new screens. CI should
block on the first three.

## When a spec is missing

Escalate rather than improvise: propose a token/pattern addition, get it into the
design system, then use it. The system grows deliberately — no one-off styles.
