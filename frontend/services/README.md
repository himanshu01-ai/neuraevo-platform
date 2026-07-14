# services/

The **API layer** — the only place that talks to the frozen backend
(`backend/app/api/v1/*`). Typed request functions + query-key registry. No React
here; hooks in `features/*/hooks/` wrap these with TanStack Query.

```
services/
├── http.ts          typed fetch client: baseURL, auth header, error mapping
├── query-keys.ts    central, hierarchical query-key factory
├── <resource>.ts    one module per backend resource (employees, tasks,
│                    workflows, memory, approvals, capabilities, health …)
└── index.ts         barrel
```

## Rules

- Every network call returns typed data validated against `types/` (Zod schemas
  at the boundary). Raw `fetch` outside `services/` is forbidden.
- Errors are normalized to one `ApiError` shape so UI error states are uniform.
- Never import React or component code here — services are framework-agnostic.
- Full contract, error model, and query-key strategy:
  [`../docs/09-state-and-api.md`](../docs/09-state-and-api.md).
- **No endpoints wired in Sprint 17.0** — architecture only. The backend is
  frozen; this layer is defined, not built.
