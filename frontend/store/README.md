# store/

**Client (UI) state** via Zustand. Ephemeral, session-scoped interface state
only — never a cache for server data (that is TanStack Query's job).

```
store/
├── ui.store.ts        sidebar collapsed, active pane, theme intent
├── command.store.ts   command-palette open state + registry
├── workspace.store.ts client-side workspace view (selected node, split ratio)
└── index.ts
```

## What belongs here vs. TanStack Query

| Client state (Zustand)              | Server state (TanStack Query)          |
| ----------------------------------- | -------------------------------------- |
| sidebar open, theme, active tab     | tasks, workflows, memory, health, …    |
| command-palette visibility          | anything fetched from the backend      |
| optimistic UI toggles, wizard step  | mutations + cache invalidation         |

## Rules

- One slice per concern; compose, don't build a god-store.
- No fetching, no domain persistence. Boundary rationale:
  [`../docs/09-state-and-api.md`](../docs/09-state-and-api.md).
