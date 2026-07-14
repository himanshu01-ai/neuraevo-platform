# 09 · State Management & API Architecture

Two state systems with a hard boundary, plus the single API layer that feeds them.

## The boundary

| Concern | Tool | Lives in |
| ------- | ---- | -------- |
| **Server state** — anything fetched from the backend (tasks, workflows, memory, approvals, health, capabilities) | **TanStack Query** | `features/*/hooks/` wrapping `services/` |
| **Client/UI state** — sidebar, theme intent, command-palette, active pane, wizard step, optimistic toggles | **Zustand** | `store/*.store.ts` |
| **Form state** — inputs, validation | **React Hook Form + Zod** | co-located in the feature/form |

**Rule:** server data is **never copied into Zustand**. The Query cache _is_ the
server-state store. Zustand holds only ephemeral interface state. This prevents
the classic dual-source-of-truth drift.

## API layer (`services/`)

The only code that talks to the frozen backend (`backend/app/api/v1/*`). No React.

```
services/
├── http.ts        typed client: baseURL (env), auth header, JSON, error mapping
├── query-keys.ts  hierarchical key factory (single source of cache keys)
├── employees.ts   tasks.ts  workflows.ts  memory.ts  approvals.ts
│                  capabilities.ts  health.ts  notifications.ts   (one per resource)
└── index.ts
```

### HTTP client contract

- Single `request()` wrapper: injects base URL + auth token, sets JSON headers,
  parses responses, and **normalizes all failures to one `ApiError`**:
  `{ status, code, message, details? }`. UI error states read this shape only.
- No raw `fetch`/`axios` anywhere else in the app.
- Responses are validated at the boundary with **Zod** and typed via `types/`.
  Backend enums map to `types/domain.ts` (UPPERCASE) — no re-casing in components.

### Query-key strategy

Central factory so invalidation is predictable:

```
queryKeys.tasks.all               ['tasks']
queryKeys.tasks.list(filters)     ['tasks','list',{…}]
queryKeys.tasks.detail(id)        ['tasks','detail', id]
queryKeys.workflows.detail(id)    ['workflows','detail', id]
queryKeys.health.summary          ['health','summary']
```

Mutations invalidate the narrowest relevant prefix. No stringly-typed keys inline.

### Query defaults (`lib/query-client.ts`)

- `staleTime` sane per resource (health short, memory longer); `retry` 1–2 with
  backoff; `refetchOnWindowFocus` off for heavy lists, on for live status.
- **Live-ish data** (running tasks, workflow progress, health): polling intervals
  or, when the backend exposes it, a streaming/subscription hook — abstracted
  behind the feature hook so components don't know the transport.

## Zustand stores

- One slice per concern (`ui.store`, `command.store`, `workspace.store`);
  compose, never a god-store. Selector-based subscriptions to avoid re-renders.
- Persist only what should survive reloads (theme, sidebar collapsed) via
  `persist` middleware; never persist server data.

## Data-flow (read + write)

```
Component ─uses→ feature hook (useTasks) ─wraps→ TanStack Query
                                   │
                                   └─calls→ services/tasks.ts ─request()→ backend
Mutation ─→ optimistic update (Query cache) ─→ server ─→ invalidate keys ─→ refetch
UI toggles (sidebar/theme) ─→ Zustand (no network)
```

## Error, loading, empty (uniform)

Every data surface renders three states from the same primitives
([04 · Components](04-component-guidelines.md)): **loading** (skeleton),
**empty** (EmptyState), **error** (ErrorState with Retry driven by `ApiError`).
Global fallbacks: `app/(app)/loading.tsx`, `app/error.tsx`, `not-found.tsx`.

## Environment & auth (architecture, not built)

- API base URL and public config via typed `lib/env.ts` (Zod-validated). Never
  hardcode URLs; never put secrets or tokens in query strings.
- Auth token handling is defined here as an interceptor in `http.ts`; the actual
  auth flow is a **later sprint** — not Sprint 17.0.

> **Sprint 17.0 scope:** this document defines the architecture. No endpoints,
> hooks, or stores are implemented now. The backend is frozen; the frontend
> adapts to it.
