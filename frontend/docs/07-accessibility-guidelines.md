# 07 · Accessibility Guidelines

Target: **WCAG 2.2 AA**. Accessibility is designed in, not audited on. A
component or screen is not "done" until it meets this bar
([08 · Developer Rules](08-developer-rules.md)).

## Color & contrast

- Body/UI text ≥ **4.5:1**; large text (≥ 18.66px bold / 24px) and meaningful
  glyphs ≥ **3:1**; UI component boundaries & focus indicators ≥ **3:1**.
- **Never encode meaning in color alone.** Status = dot/icon **+** label (the
  StatusBadge enforces this). Charts use shape/label, not hue only.
- Verify both themes. Dark mode is not exempt — check `muted-foreground` on
  `card`/`muted`.

## Keyboard

- **Everything operable by keyboard.** No mouse-only actions.
- Logical tab order following visual order. `Tab`/`Shift+Tab` move; `Enter`/
  `Space` activate; `Esc` closes overlays; arrow keys drive menus, tabs
  (roving tabindex), and the workflow graph selection.
- **Global shortcuts:** ⌘K/Ctrl-K command palette; `/` focus search; `g` then a
  key for go-to navigation (documented in-app). Never trap the user.
- Provide a **"Skip to content"** link as the first focusable element.

## Focus

- Visible `:focus-visible` ring (2px `ring` + 2px offset) is global in
  `globals.css`. Do not remove outlines without an equal replacement.
- Overlays (dialog, drawer, menu, palette) **trap focus** while open and
  **restore** focus to the trigger on close.

## Semantics & ARIA

- Prefer native elements (`button`, `a`, `nav`, `main`, `header`, `ul`) over
  ARIA-retrofitted `div`s. One `<main>`, landmark regions for nav/header.
- Use shadcn/Radix primitives — they ship correct roles, `aria-*`, and focus
  management. Don't hand-roll a dialog/menu/tabs.
- Icon-only buttons need `aria-label`. Decorative icons/illustrations get
  `aria-hidden`. Live regions (`aria-live="polite"`) announce task/run status
  changes and toasts.
- Forms: every input has a programmatic label; errors use `aria-invalid` +
  `aria-describedby`; RHF + Zod messages are announced.

## Motion & sensory

- Honor `prefers-reduced-motion` globally (already enforced) — reduced-motion is a
  full, legible path, not a degraded one. The AI Core renders a static frame.
- No content conveyed only by animation, sound, or the 3D scene. Nothing
  auto-plays audio. No flashing > 3×/sec.

## Content & media

- Meaningful images/logos have `alt`; decorative ones have empty `alt`/
  `aria-hidden`. SVG marks include `role="img"` + `aria-label` (see brand assets).
- Copy is plain-language; error states explain cause + recovery, not codes.

## Targets & zoom

- Touch targets ≥ **24×24px** (prefer 40px on mobile controls). Layout reflows and
  stays usable at **200% zoom** and **320px** width with no loss of function.

## Definition of done (a11y)

Keyboard-complete · visible focus + trap/restore · AA contrast (both themes) ·
correct roles/labels · reduced-motion safe · status not color-only · forms
labeled + errors announced · screen-reader pass on primary flow.
