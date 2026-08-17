# 12 · Navigation Architecture

Information architecture, the route map, and the navigation model. Navigation is
**flat and fast** — every primary screen is one click (or one ⌘K) away.

## Information architecture

```
NeuraEvo
├── Home                     what is happening
├── Workspace                what the AI is doing        (?task=)
├── Tasks                    everything delegated
│   └── Task detail → Workspace
├── Workflow                 how work is progressing      (?run=)
├── Memory                   what it knows
├── Dashboard                is the system healthy
├── Capabilities            (grouped)
│   ├── Files
│   ├── Browser
│   ├── Python
│   ├── Email
│   ├── Calendar
│   └── GitHub
└── Settings                 how it's configured
    ├── Profile · Employee/Blueprint · Approvals
    └── Capabilities · Appearance · Account
```

## Route map (App Router)

```
app/
├── (marketing)/
│   └── page.tsx                    /                Home hero (public)
└── (app)/
    ├── layout.tsx                  AppShell (sidebar + top nav + providers)
    ├── page.tsx                    /app             Home (status overview)
    ├── workspace/page.tsx          /app/workspace   (?task=<id>)
    ├── tasks/
    │   ├── page.tsx                /app/tasks
    │   └── [taskId]/page.tsx       /app/tasks/:id   → redirects into Workspace
    ├── workflow/page.tsx           /app/workflow    (?run=<id>)
    ├── memory/page.tsx             /app/memory
    ├── dashboard/page.tsx          /app/dashboard
    ├── files/page.tsx              /app/files
    ├── browser/page.tsx            /app/browser
    ├── python/page.tsx             /app/python
    ├── email/page.tsx              /app/email
    ├── calendar/page.tsx           /app/calendar
    ├── github/page.tsx             /app/github
    └── settings/
        ├── page.tsx                /app/settings    → /app/settings/profile
        └── [section]/page.tsx      /app/settings/:section
```

Route groups: `(marketing)` public shell, `(app)` authenticated shell. Screens are
**deep-linkable**; Workspace/Workflow read the active entity from a query param so
links from Home/Tasks/notifications land in context.

> Routes are **not implemented** in Sprint 17.0 — this is the map future sprints
> build to. Auth gating of `(app)` is a later sprint.

## Navigation model (three surfaces)

1. **Sidebar (primary).** Persistent rail. Order: Home · Workspace · Tasks ·
   Workflow · Memory · Dashboard — then **Capabilities** group (Files, Browser,
   Python, Email, Calendar, GitHub) — then **Settings** pinned bottom. Active
   route highlighted; collapses to icons (tooltips) and to a bottom tab bar on
   mobile ([05](05-layout-guidelines.md), [10](10-responsive-guidelines.md)).

2. **Command Palette (fast path).** ⌘K/Ctrl-K. Sections: **Navigate** (jump to any
   screen), **Delegate** (start a task), **Actions** (contextual), **Search**
   (entities). The Raycast/Linear-style accelerator; every screen registers its
   nav entry and key actions here.

3. **Contextual.** Breadcrumb/title in the Top Nav; in-page **Tabs** for section
   switching (never for primary nav); deep links from Home cards, Tasks rows, and
   notifications into Workspace/Workflow/capability detail.

## Navigation registry (single source)

Sidebar items **and** Command-Palette "Navigate" entries come from one typed
registry (`layouts/` + a nav config) so they never diverge. Each entry:
`{ id, label, href, icon (Lucide), group, order }`. Capability entries derive from
`CAPABILITIES` in `types/domain.ts`, keeping nav aligned with the backend.

## Wayfinding rules

- Depth ≤ 2 from any screen to any other (sidebar or ⌘K).
- Current location is always obvious (active sidebar item + Top Nav title).
- Back/forward and refresh preserve state via URL params, not hidden client state.
- Notifications and Home cards are **entry points**, deep-linking into the right
  screen and entity.
- Mobile: bottom tabs for the top 4–5 destinations; the rest live in the drawer.
