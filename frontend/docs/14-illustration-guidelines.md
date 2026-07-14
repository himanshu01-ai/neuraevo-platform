# 14 · Illustration Guidelines

Illustration and 3D in NeuraEvo — how visual richness is used without breaking the
calm, enterprise character. Extends the illustration/3D notes in
[02 · Brand](02-brand-guidelines.md) and the motion rules in
[03 · Motion](03-motion-guidelines.md).

## Philosophy

- **Restraint is the brand.** Illustration is an accent, never wallpaper. The
  product reads as neutral and precise; visuals punctuate, they don't fill.
- **Geometric, line-led, low-detail.** Thin strokes, generous negative space, at
  most a two-stop violet gradient on an otherwise neutral scene.
- **Abstract over literal.** Evoke intelligence, flow, and evolution (nodes,
  fields, paths) — never stock 3D people, mascots, skeuomorphism, or clip-art.
- **Never behind data.** No illustration or texture behind tables, forms, dense
  content, or long text.

## 3D illustration usage

- **Allowed only** for: the hero, the **AI Core**, workflow visualization accents,
  and premium loading. **Never** for forms, tables, settings, or navigation
  ([02 · Brand](02-brand-guidelines.md)).
- Built with **React Three Fiber** (`@react-three/fiber` + `drei`), isolated in
  `components/brand/*` as client leaves. 3D never blocks interaction or content.
- **AI Core** = a slowly evolving node-field / soft volumetric form in NeuraEvo
  Violet on a dark ground, subtle bloom. Matte materials, low saturation, gentle
  ambient motion. It is decorative — it never encodes required information.

## Hero illustrations

- One focal visual (AI Core or an abstract violet field) behind/beside the Home
  hero and marketing. Text and CTAs always sit on a legible surface, not directly
  on busy geometry.
- Keep contrast for overlaid copy at AA; add a scrim/`surface-glass` layer if the
  visual would reduce legibility. The hero visual scales down and simplifies on
  small/low-power devices ([10 · Responsive](10-responsive-guidelines.md)).

## Empty states

- Simple line illustration or a 32–48px icon ([13 · Icons](13-icon-system.md)),
  not a full scene. Calm tone (neutral/brand), never an error look.
- Composition: illustration → one-line title → supporting sentence → one primary
  action ([04 · Components](04-component-guidelines.md)). Every list/screen defines
  its own.

## Onboarding illustrations

- A small, consistent set of line illustrations that explain the delegate → plan →
  execute → approve model. Same stroke/tone family as icons; no photographic or
  3D-people imagery.
- Sequential, quiet, skippable; motion is subtle entrance only.

## AI workflow graphics

- The workflow graph is **functional UI**, not illustration — nodes/edges follow
  [04 · Components](04-component-guidelines.md) and [11 · Screens](11-screen-architecture.md),
  status-tone colored. Any decorative flourish (ambient particles along the active
  path, faint grid) stays behind the nodes and must not reduce contrast or
  distract from state.

## Background graphics

- Backgrounds default to solid theme surfaces (`background`/`card`). Optional
  accents only: a very faint dot grid, a low-opacity radial violet glow behind a
  hero, or a hairline gradient border. Opacity kept low enough to preserve AA text
  contrast; never animated behind text.

## Glassmorphism

- Reserved for **floating chrome over content**: the top nav, command palette, and
  occasionally popovers/hero cards. Use the `surface-glass` utility (translucent
  background + backdrop blur).
- Rules: only over content that can afford blur; maintain AA contrast for text on
  glass (add opacity/scrim if needed); never stack multiple glass layers; never
  use glass for dense data surfaces (tables, forms).

## Gradients

- **One family only:** NeuraEvo Violet, max two stops (`brand.400 → brand.600`),
  low-angle. Used for: the AI Core, hero accents, progress fills, and hairline
  gradient borders on premium/AI cards.
- **Never** put a gradient on body text, on the logo, behind data, or as a
  full-page background. No multi-hue or rainbow gradients — the accent stays
  singular ([02 · Brand](02-brand-guidelines.md)).

## Lighting

- Soft, single-source, low-contrast. In 3D: gentle ambient + one soft key light,
  matte materials, restrained bloom — premium, never glossy or toy-like.
- Elevation in UI comes from hairline borders and low shadows first
  ([01 · Design System](01-design-system.md)); light effects are subtle, not
  dramatic. Dark mode leans on surface lightness, not heavy glow.

## Motion

- Illustration/3D motion is **ambient and non-blocking**: slow, low-amplitude
  loops (`ambient`, `pulse-glow`) that pause when the tab is hidden.
- No parallax on scroll, no attention-seeking loops in the work area, no motion
  that delays input. Full rules in [03 · Motion](03-motion-guidelines.md).

## Performance

- 3D is **lazy-loaded** (`next/dynamic`, client-only) and mounted only where
  allowed; it never blocks first paint or hydration of real content.
- Budget: cap draw calls / triangle count; pause the render loop when offscreen or
  tab-hidden; throttle to a sensible frame cap. Provide a lightweight static
  fallback (image/SVG) for mobile, low-power, and slow connections.
- Illustrations are optimized SVG (inline or `next/image`); raster art uses
  AVIF/WebP with responsive sizes. No uncompressed PNGs, no giant hero videos.

## Accessibility

- Decorative illustrations/3D: `aria-hidden`, empty `alt`. They never carry
  information needed to use the product.
- Honor `prefers-reduced-motion`: 3D renders a **static frame**, ambient loops
  stop (global rule + `MotionProvider`). Reduced-motion is a full path, not a
  degraded one ([07 · Accessibility](07-accessibility-guidelines.md)).
- Maintain AA text contrast over any illustration, glass, or gradient — add a
  scrim rather than compromise legibility. No essential meaning conveyed by
  imagery alone.

## Developer rules

- 3D/illustration lives in `components/brand/*`, client-only, lazy-loaded; **never**
  in forms, tables, settings, or navigation.
- Colors/gradients from tokens only — single violet family, ≤ 2 stops, no
  hardcoded hex.
- Provide a static fallback and respect reduced-motion for every animated visual.
- Keep assets optimized (SVG/AVIF/WebP) and within the performance budget; measure
  before shipping.
- When in doubt, use less — restraint is the default.
