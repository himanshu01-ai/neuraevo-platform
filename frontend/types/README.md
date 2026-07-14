# types/

**Global, shared TypeScript types** — the vocabulary the whole app agrees on.
Feature-local types live in `features/<domain>/types.ts`.

```
types/
├── domain.ts   status/approval/node enums, capabilities, tone maps
│                — mirrors the frozen backend contracts   [implemented]
├── api.ts      request/response DTO shapes + ApiError     (later)
└── index.ts    barrel                                     (later)
```

## Rules

- `domain.ts` is the **canonical status vocabulary** (`LifecycleStatus`,
  `ApprovalStatus`, `NodeStatus`, `Capability`, tone maps). It must not drift
  from `backend/app/services/ai_employee/*`. Backend values stay UPPERCASE;
  UI labels are provided by the `*_LABEL` maps.
- Types only — no runtime logic beyond `as const` literal maps used for tone/label.
