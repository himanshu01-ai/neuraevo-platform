# app/

Next.js 15 **App Router**. Routing, layouts, server components, and route-level
data orchestration only. No design tokens, no reusable UI, no business rules.

## Conventions

- **Route groups** organize without affecting the URL:
  - `(marketing)/` — public hero / landing (uses the brand hero + 3D AI Core).
  - `(app)/` — the authenticated product shell (sidebar + top nav + content).
- Each screen is a thin **route segment** that composes a `features/<domain>`
  module. Pages wire data + layout; they never contain feature logic.
- `layout.tsx` files compose `layouts/` primitives; they do not define new chrome.
- `loading.tsx` / `error.tsx` / `not-found.tsx` per segment use the shared
  Loading, Error, and Empty states from `components/`.

## Planned segment map (Sprint 17.0 defines, later sprints implement)

```
app/
├── layout.tsx                 root: fonts, providers, <html class theme>
├── (marketing)/page.tsx       Home hero (public)
└── (app)/
    ├── layout.tsx             AppShell (sidebar + topnav)
    ├── page.tsx               Home (status overview)
    ├── workspace/             AI Workspace
    ├── tasks/                 Tasks
    ├── workflow/              Workflow graph
    ├── files/ browser/ python/ email/ calendar/ github/   Capabilities
    ├── memory/                Memory
    ├── dashboard/             System health
    └── settings/              Configuration
```

Do **not** create these routes in this sprint — this is the architecture only.
See [`../docs/12-navigation-architecture.md`](../docs/12-navigation-architecture.md).
