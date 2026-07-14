# features/

**Vertical domain slices.** Each feature owns its components, hooks, and local
types for one product area. This is where business UX lives — assembled from
`components/` primitives and fed by `services/` + `hooks/`.

```
features/
└── <domain>/            e.g. workspace, tasks, workflow, memory, dashboard,
    ├── components/      capabilities (browser, python, files, email, …)
    ├── hooks/           feature data hooks (wrap TanStack Query)
    ├── types.ts         feature-local types (extend types/domain.ts)
    └── index.ts         public surface consumed by app/ routes
```

## Rules

- A route in `app/` imports **only** a feature's `index.ts` — never reaches into
  its internals.
- Features may depend on `components/`, `services/`, `store/`, `hooks/`, `lib/`,
  `types/`. Features must **not** import from other features (share via
  `components/` or `lib/` instead) — this keeps slices independent.
- No feature code in this sprint. Sprint 17.0 defines the boundary and the
  screen specs in [`../docs/11-screen-architecture.md`](../docs/11-screen-architecture.md).
