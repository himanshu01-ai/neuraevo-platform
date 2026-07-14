# 06 · Frontend Architecture

The production folder architecture and the import/dependency rules that keep it
scalable. This mirrors the discipline of the frozen backend (locked layers, clear
ownership, additive-only) on the frontend.

## Folder map

```
frontend/
├── app/            Next.js App Router: routes, layouts, server components
├── components/     reusable domain-agnostic UI  (ui/ · patterns/ · brand/)
├── features/       vertical domain slices (workspace, tasks, workflow, …)
├── layouts/        app-shell chrome (AppShell, Sidebar, TopNav, MobileNav)
├── hooks/          cross-cutting React hooks
├── services/       API layer — the only code that talks to the backend
├── store/          Zustand client/UI state
├── types/          global shared types (domain.ts mirrors backend)
├── styles/         globals.css — CSS-variable theme contract
├── providers/      root React context providers
├── lib/            framework-aware shared infra (cn, query-client, env, fonts)
├── utils/          pure dependency-free helpers
├── design-system/  design tokens (visual-language source of truth)
├── assets/         brand + static media
└── docs/           these guidelines
```

Each folder has a `README.md` stating its purpose and placement rules. Read the
folder README before adding a file to it.

## Dependency direction (the golden rule)

Imports flow **downward only**. A layer may import from layers below it, never
above, never sideways across siblings.

```
app  ──▶ layouts ──▶ features ──▶ components ──▶ design-system
 │          │           │            │               ▲
 │          │           ├──▶ services ──▶ types ──────┘
 │          │           ├──▶ store
 │          │           └──▶ hooks
 └──────────┴──────────────▶ lib · utils · providers  (leaf infra)
```

- **`app/`** is thin: routing, layout composition, and data orchestration. No
  design tokens, no reusable UI, no business rules.
- **`features/`** own domain UX. A feature may use `components`, `services`,
  `store`, `hooks`, `lib`, `utils`, `types`. A feature **must not** import another
  feature (share via `components/` or `lib/`).
- **`components/`** are presentational and domain-agnostic — they never import
  `features/`, `services/`, or `store/`.
- **`services/`** are framework-agnostic (no React) and the sole backend caller.
- **`design-system/`, `lib/`, `utils/`, `types/`** are leaves — they import from
  nothing above them.

## Server vs. client components

- **Default to Server Components.** Data fetching, static composition, and layout
  render on the server.
- Add `"use client"` only for interactivity: state, effects, event handlers,
  Framer Motion, R3F, Zustand, forms. Push the boundary as low as possible — a
  client leaf inside a server tree, not a client root.
- Providers, the command palette, motion, and 3D are client; the shell frame and
  most page scaffolding are server.

## Boundaries (locked)

- **UI never fetches directly.** All network I/O goes through `services/`, wrapped
  by TanStack Query hooks in `features/*/hooks/`. No `fetch`/`axios` in components.
- **Server data is never mirrored into Zustand.** Client state (Zustand) and
  server cache (Query) are separate concerns — see [09](09-state-and-api.md).
- **No hardcoded design values.** Color/spacing/radius/motion come from tokens and
  Tailwind utilities only.
- **`types/domain.ts` mirrors the backend** and must not drift from
  `backend/app/services/ai_employee/*`.

## Path aliases

`@/*` → `frontend/*`, with `@/components/*`, `@/features/*`, `@/lib/*`,
`@/hooks/*`, `@/services/*`, `@/store/*`, `@/types/*`, `@/design-system/*`
(see `tsconfig.json`). Always import via alias, never deep relative `../../../`.

## Adding a new screen (recipe for future sprints)

1. Define/confirm types in `types/` or `features/<domain>/types.ts`.
2. Add service functions + query keys in `services/`.
3. Build the feature in `features/<domain>/` (components + hooks).
4. Add the route in `app/(app)/<screen>/` composing the feature.
5. Register the route in the Sidebar + Command Palette navigation registry.
6. Meet the definition of done ([08 · Developer Rules](08-developer-rules.md)).

## Extensibility

Architecture is **additive**: new capabilities/screens slot into `features/` and
`app/` without touching existing slices. No new top-level folders — the 14 defined
here are the complete set.
