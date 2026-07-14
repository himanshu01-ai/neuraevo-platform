# 17 · Design Review Checklist

The production sign-off gate for any screen or component before release. Every box
must be checked (or explicitly N/A) — a "no" blocks release. Pairs with the
definition-of-done in [08 · Developer Rules](08-developer-rules.md) and
[16 · Coding Rules](16-coding-rules.md).

## Design consistency

- [ ] Matches the design-system language ([01](01-design-system.md)); no bespoke,
      off-system styling.
- [ ] Reuses existing primitives/patterns before introducing anything new.
- [ ] One primary action; screen answers its **one question**
      ([00](00-overview.md)) in the first viewport.
- [ ] Brand usage correct (logo, accent, voice) — [02](02-brand-guidelines.md).

## Typography

- [ ] Uses named text roles / scale ([01](01-design-system.md)); no off-scale sizes.
- [ ] 14px UI baseline; prose 16px; headings 600, tracking correct.
- [ ] `--font-sans` for UI, `--font-mono` for code/IDs/metrics.
- [ ] No orphaned/overflowing text; sensible line length and truncation.

## Color tokens

- [ ] All colors from tokens/CSS variables — **zero hardcoded hex / arbitrary
      values**.
- [ ] Accent (violet) used sparingly (≤ ~10% of viewport), not as a text background.
- [ ] Semantic colors used only for their meaning (success/warning/danger/info).

## Spacing

- [ ] 4px grid throughout; spacing roles honored (`card`/`field`/`section`/`gutter`).
- [ ] Consistent rhythm; no arbitrary paddings/margins; aligned to the grid.

## Responsive layouts

- [ ] Verified at 375 / 768 / 1280 / 1920 (+ 320px & 200% zoom).
- [ ] Sidebar → bottom tabs/drawer < md; multi-pane → stacked drill-in on mobile.
- [ ] No page-level horizontal scroll; wide content scrolls within its own region.
- [ ] Media responsive (`max-width:100%`, sized `next/image`). [10](10-responsive-guidelines.md)

## Accessibility

- [ ] AA contrast in **both** themes (text 4.5:1, large/UI 3:1).
- [ ] Correct semantics/roles; icon-only controls labeled; landmarks present.
- [ ] Forms labeled; errors `aria-invalid` + `aria-describedby` + announced.
- [ ] Status/meaning never color-only (dot/icon + label). [07](07-accessibility-guidelines.md)

## Keyboard navigation

- [ ] Every action reachable and operable by keyboard; logical tab order.
- [ ] Visible `:focus-visible`; overlays trap and restore focus; `Esc` closes.
- [ ] ⌘K palette, `/` search, and documented shortcuts work; no key traps.
- [ ] "Skip to content" present at the app level.

## Motion

- [ ] Durations/easings from motion tokens; UI motion ≤ 320ms; nothing blocks input.
- [ ] `prefers-reduced-motion` honored (animations collapse; 3D static frame).
- [ ] Only the changed element animates; no gratuitous loops in the work area. [03](03-motion-guidelines.md)

## Performance

- [ ] Server-first; heavy/3D lazy-loaded; per-icon imports; no `import *`.
- [ ] Skeleton/empty/error states present; optimistic UI where it helps.
- [ ] No layout shift (CLS); long lists/tables virtualized; images optimized.
- [ ] 3D within budget (offscreen pause, static fallback). [14](14-illustration-guidelines.md)

## Dark mode

- [ ] Fully themed via CSS variables; visually verified in dark **and** light.
- [ ] Elevation reads correctly (surface lightness in dark, not heavy shadow).
- [ ] No token drift between `tokens/color.ts` and `styles/globals.css`.

## Status colors

- [ ] Statuses resolved via `types/domain.ts` (`status → tone → color`), not
      inline conditionals.
- [ ] Lifecycle/approval/node/health icons match the canonical map
      ([13 · Icons](13-icon-system.md)); badge + icon agree.

## Component consistency

- [ ] Uses shared components; variants via CVA; accepts `className`, forwards refs.
- [ ] All states covered: default/hover/focus/active/disabled/loading/error/empty.
- [ ] Matches specs in [04 · Components](04-component-guidelines.md); no one-off variants.

## Backend compatibility

- [ ] Domain vocabulary matches the frozen backend (UPPERCASE enums via
      `types/domain.ts`); no re-casing/invented states.
- [ ] All data access through `services/` + Query; `ApiError` handled; no direct
      `fetch`. Backend untouched. [09](09-state-and-api.md)

## No hardcoded values

- [ ] No hardcoded colors, spacing, radius, shadow, z-index, durations, or URLs.
- [ ] No mixed icon libraries; no emoji as UI; Lucide only, 1.5px stroke,
      on-scale sizes. [13](13-icon-system.md)
- [ ] No `any`/unjustified `!`/`@ts-ignore`; alias imports only.

## Release readiness

- [ ] `typecheck`, `lint`, `format` clean; no broken imports; no console errors.
- [ ] Deep-linkable route; registered in Sidebar + Command Palette.
- [ ] Loading/empty/error verified against real-shaped data; Lighthouse a11y ≥ 95.
- [ ] Additive only — no regression to Sprint 17.0 foundation or completed work.
- [ ] Reviewer sign-off recorded on the PR.
