# providers/

**React context providers** mounted once at the root (`app/layout.tsx`). The
composition root for cross-cutting runtime concerns.

Anticipated providers (defined here, implemented in a later sprint):

- `ThemeProvider` — light/dark/system via `next-themes`, sets the `.dark` class.
- `QueryProvider` — the TanStack `QueryClient` (retry, staleTime defaults).
- `MotionProvider` — Framer Motion `MotionConfig` honoring reduced-motion.
- `CommandPaletteProvider` — mounts the ⌘K launcher globally.
- `ToastProvider` — notification surface.

They nest in this order (outermost → innermost): Theme → Query → Motion →
CommandPalette → Toast.

## Rules

- Providers are infrastructure, not features. No domain logic.
- Keep each provider a thin wrapper; configuration lives in `lib/` where reusable.
