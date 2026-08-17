# hooks/

**Cross-cutting React hooks** reused by more than one feature. Feature-specific
data hooks live in `features/<domain>/hooks/`; only shared ones belong here.

Examples this foundation anticipates (not implemented in Sprint 17.0):

- `useMediaQuery` / `useBreakpoint` — responsive branching against tokens.
- `useReducedMotion` — reads the OS preference for the motion system.
- `useCommandPalette` — ⌘K open/close + registry.
- `useTheme` — light/dark/system (wraps `next-themes`).
- `useHotkeys` — global keyboard shortcuts.

## Rules

- Hooks are UI/utility concerns. Anything that fetches domain data belongs in a
  `features/*/hooks/` hook wrapping TanStack Query — see
  [`../docs/09-state-and-api.md`](../docs/09-state-and-api.md).
- Pure and side-effect-light; no direct `fetch` (go through `services/`).
