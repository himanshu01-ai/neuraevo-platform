# 03 · Motion Guidelines

Motion is **calm, fast, and purposeful**. It orients the user through state
changes and reinforces hierarchy — it never performs. Tokens live in
`design-system/tokens/motion.ts` and Tailwind `animation`/`keyframes`.

## Principles

1. **Purpose over polish** — every animation clarifies a change (enter, exit,
   progress, success). If it doesn't communicate, remove it.
2. **Short** — UI motion is 120–320ms. Nothing routine exceeds `slow` (320ms).
   Only ambient AI-Core loops run long, and they are non-blocking.
3. **One thing moves** — animate the element that changed, not the whole screen.
4. **Physical, not bouncy** — decisive entrance, soft settle. Springs are
   restrained; `emphasized` overshoot is reserved for success moments.
5. **Never block** — motion is never on the critical path to interaction. Content
   is usable before/while it animates in.

## Duration & easing tokens

| Token | ms | Use |
| ----- | -- | --- |
| `fast` | 120 | hover, press, toggle, micro-interactions |
| `base` | 200 | dropdowns, tabs, popovers, default enter/exit |
| `slow` | 320 | dialogs, drawers, section transitions |
| `slower` | 480 | route transitions, large surfaces |
| `ambient` | 4000 | idle AI-Core pulse (loops) |

| Easing | Curve | Use |
| ------ | ----- | --- |
| `standard` | `0.2,0,0,1` | most UI |
| `entrance` | `0.16,1,0.3,1` | elements arriving |
| `exit` | `0.4,0,1,1` | elements leaving |
| `emphasized` | `0.34,1.56,0.64,1` | success / delight only |

Named `transition` presets (`hover`, `enter`, `exit`, `panel`, `route`) are
ready to spread into Framer Motion props.

## Patterns

### Page / route transitions

- Content fades + rises 8px (`fade-up`, `entrance`, 320–480ms). The app shell
  (sidebar, top nav) is **persistent** and does not re-animate between routes.
- No horizontal slides between top-level screens (that implies spatial hierarchy
  we don't have).

### Hover & press

- Hover: 120ms background/border tint (`accent`, `press` opacity for active).
- Press: scale to 0.98 on primary buttons, 60–90ms, spring-back. Never on
  large surfaces.

### Loading

- **Skeletons first**, spinners rarely. Skeletons use the `shimmer` keyframe
  (1.6s) over `muted`. A spinner appears only for indeterminate < 1s actions.
- Prefer **optimistic UI** for mutations; reconcile on server response.

### Workflow & progress animation

- Workflow nodes transition state with a color-tone crossfade (`base`, 200ms) and
  a soft ring pulse while `RUNNING`.
- Edges animate a subtle directional dash flow only along the active path.
- Progress bars/rings ease width/stroke with `standard`; completion triggers a
  single `emphasized` tick on the success icon.

### Micro-interactions

- Toggle/checkbox/switch: 120ms. Copy-to-clipboard: icon swap + 1s revert.
- Toasts: enter `entrance` from the corner (240ms), auto-dismiss with a quiet
  progress hairline. Command palette: `base` fade + 4px rise, no zoom.

### AI Core (3D / ambient)

- Slow, continuous, low-amplitude (`ambient`, `pulse-glow`). Pauses when the tab
  is hidden. Purely decorative — never conveys required information.

## Reduced motion (mandatory)

- The global rule in `styles/globals.css` collapses all animation/transition to
  ~0ms under `prefers-reduced-motion: reduce`.
- In JS, wrap Framer Motion in a `MotionProvider` (`MotionConfig reducedMotion=
  "user"`) and gate bespoke animations with a `useReducedMotion` hook.
- Reduced-motion is a **first-class path**: state still changes instantly and
  legibly (opacity swaps, no transform), the AI Core renders a static frame.

## Anti-patterns

- No parallax on scroll, no auto-playing carousels, no attention-seeking loops in
  the work area, no animated gradients behind text, no motion that delays input.
