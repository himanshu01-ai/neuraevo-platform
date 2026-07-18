# Frontend Release Candidate (RC1)

Status of the NeuraEvo web frontend at the end of **Sprint 17.12**, immediately
before Sprint 18 backend integration.

This document is the handover contract between the frontend (Sprints 17.0–17.12)
and the integration work that follows. It records what is built, what is real,
what is deliberately mocked, and exactly where the backend plugs in.

> **The single most important fact for Sprint 18:** every workspace reads its
> data through one adapter interface per domain. Integration means writing a new
> adapter class and changing one line in that domain's service file. No
> component, hook, store, or route changes.

---

## 1. Architecture overview

### Stack

| Concern | Choice |
| --- | --- |
| Framework | Next.js 15 (App Router, React Server Components where possible) |
| Language | TypeScript (strict, `noUncheckedIndexedAccess`) |
| Styling | Tailwind CSS with a semantic design-token layer |
| Server state | TanStack Query |
| Client state | Zustand |
| Motion | Framer Motion + a global reduced-motion CSS rule |
| Icons | lucide-react |

> The platform doc in `CLAUDE.md` lists React Native under Frontend. That
> predates Sprint 17.0, which established this workspace as a **Next.js web
> app**. The web app is the shipped surface; nothing here is React Native.

### Layer boundaries

```
app/            Routes only — metadata, dynamic imports, params. No logic.
  └── layout / error / loading / not-found boundaries
features/       Screens and domain components. Composes UI + hooks.
  └── <domain>/components | hooks | models | <sub-areas>
services/       Domain contracts + adapters. The backend seam.
  └── <domain>/types | fixtures | mock-adapter | <domain>-service | keys
store/          Zustand. Client state only — never server data.
components/     Shared, domain-agnostic UI primitives.
hooks/          Shared, domain-agnostic hooks.
utils/          Pure helpers. No React, no I/O, no tokens.
types/domain.ts Backend-mirrored vocabularies shared across domains.
```

The dependency direction is strictly one-way:

```
app → features → services → (adapter)
             ↘ store
             ↘ components / hooks / utils
```

A feature never imports another feature's internals; it imports that feature's
barrel (`features/<domain>/index.ts`) if it needs anything at all. Services never
import features. Components never import services.

---

## 2. Workspace inventory

Ten surfaces, 46 routes.

| Workspace | Sprint | Routes | Notes |
| --- | --- | --- | --- |
| Landing | 17.1 | `/` | Marketing shell, brand system |
| Authentication | 17.2 | `/login` `/signup` `/forgot-password` `/verify-email` | Route-grouped `(auth)` |
| Onboarding | 17.3 | `/onboarding` | Interview-driven employee creation |
| Workspace shell | 17.0/17.4 | `/workspace` | Sidebar, top bar, breadcrumbs, command palette, mobile drawer |
| Dashboard | 17.4 | `/workspace` | Overview widgets |
| Workflow Builder | 17.5 | `/workspace/workflows` + 5 | Canvas, nodes, edges, templates, settings |
| AI Employees | 17.6 | `/workspace/employees` + 4 | Directory, profile, editor, templates |
| Tasks | 17.7 | `/workspace/tasks` + 5 | Board, execution graph, queue, approvals, history |
| Memory | 17.8 | `/workspace/memory` + 8 | Browser, graph, collections, timeline, insights, search |
| Conversations | 17.9 | `/workspace/conversations` + 5 | Thread, composer, context panel, search, settings |
| Collaboration | 17.10 | `/workspace/collaboration` + 5 | Notifications, inbox, activity, approvals, mentions, team |

`/workspace/[...segments]` is a catch-all that renders an in-shell "coming soon"
placeholder, so an unknown workspace path never dead-ends in a 404.

---

## 3. Adapter architecture

### The seam

Each domain in `services/` follows one shape:

```
services/<domain>/
  types.ts              Contracts + the <Domain>Adapter interface
  fixtures.ts           Deterministic mock data
  mock-adapter.ts       Mock implementation of the interface
  <domain>-service.ts   Singleton: picks the adapter, exposes flat methods
  keys.ts               TanStack Query key factory
  index.ts              Public surface
```

`<domain>-service.ts` is the only file that names a concrete adapter:

```ts
const adapter: TasksAdapter = new MockTasksAdapter();

export const taskService = {
  list: () => adapter.list(),
  detail: (id: string) => adapter.detail(id),
  // …
};
```

### The eight adapter interfaces

| Interface | Domain |
| --- | --- |
| `AuthAdapter` | Session, login, signup, verification |
| `DashboardAdapter` | Overview metrics |
| `EmployeesAdapter` | Employee CRUD, capabilities, activity |
| `WorkflowsAdapter` | Workflow definitions, graphs, templates |
| `TasksAdapter` | Tasks, execution graph, queue, approvals, artifacts |
| `MemoryAdapter` | Memory CRUD, search, graph, insights |
| `ConversationsAdapter` | Conversations, messages, search, suggestions |
| `CollaborationAdapter` | Notifications, activity, mentions, approvals, counts |

**Sprint 18 must not change these interfaces.** They are the contract the whole
UI is written against. If the backend shape differs, the adapter translates —
that is the adapter's job.

### Rules the adapters keep

- **No clock reads.** Timestamps are fixture-pinned or derived from prior state
  (e.g. "previous message + 1 minute"). The same actions always produce the same
  bytes, which is what makes SSR and hydration agree.
- **No randomness.** Ids are derived from existing rows, never `Math.random()`.
- **Persistence is simulated** via `localStorage` so a user edit survives a
  reload. Keys are listed in §9.
- **Latency is simulated** (~350 ms) so loading states are exercised in
  development rather than only in production.

---

## 4. State management

The split follows `docs/09-state-and-api.md`:

### Server state — TanStack Query

All remote-shaped data. Seven key factories (`services/<domain>/keys.ts`) with
hierarchical keys so a mutation can invalidate one record or a whole list:

```ts
export const taskKeys = {
  all: ["tasks"],
  lists: ["tasks", "list"],
  detail: (id) => ["tasks", "detail", id],
  // …
};
```

Feature hooks (`features/<domain>/hooks/use-<domain>.ts`) wrap the service so no
component ever calls an adapter directly.

**Polling is deliberately off.** Live surfaces — the task board, the notification
feed, a conversation thread — are exactly where polling belongs, and each hook
carries a comment marking the spot. Nothing polls today because the mock
advances nothing on its own: a refetch would return identical bytes and cost a
render for no news. Sprint 18 switches this on inside the hook; no component
changes.

### Client state — Zustand

Only the questions the user is asking of the data: selections, filters, sort,
view mode, panel visibility, composer drafts. Never server data.

| Store | Persists |
| --- | --- |
| `store/ui` | `sidebarCollapsed` |
| `store/auth` | *(nothing — bootstrapped per session by design)* |
| `store/employees` | `viewMode` |
| `store/workflow` | canvas preferences |
| `store/tasks` | `viewMode` |
| `store/memory` | `viewMode` |
| `store/conversations` | `contextPanelOpen` |
| `store/conversations` (composer) | per-conversation drafts |
| `store/collaboration` | `viewMode` |

Each store uses `persist` with `partialize` so only durable *preferences*
survive a reload. A filter or a selection is a moment, not a setting.

---

## 5. Shared component architecture

### Primitives (`components/ui`)

22 domain-agnostic primitives: `alert`, `avatar`, `badge`, `button`, `card`,
`checkbox`, `dropdown-menu`, `empty-state`, `error-state`, `field`, `input`,
`label`, `loading-state`, `option-card`, `progress`, `select`, `shimmer`,
`skeleton`, `spinner`, `status-badge`, `textarea`, `tooltip`.

Two carry the design system's status contract:

- **`status-badge`** resolves every backend status → a `StatusTone` → a colour,
  through the maps in `types/domain.ts`. Status is never coloured inline, and
  always pairs a dot with a label so colour is never the sole carrier.
- **`TONE_VARIANT` / `TONE_DOT`** are the exported tone→class maps other
  surfaces reuse rather than re-deriving.

### Consistency contracts

| Concern | Contract |
| --- | --- |
| Empty | `EmptyState` — calm tone, never an error look |
| Loading | `LoadingState` / `Skeleton` / per-feature skeletons matching final layout |
| Error | `ErrorState` with `onRetry` wired to the query's `refetch` |
| Focus | `focus-visible:ring-2 ring-ring` on every interactive element |
| Motion | `Reveal` for sections; per-item stagger for feeds |
| Drawers | `useDrawerDismiss` — Escape + breakpoint-gated scroll lock |

### Two reference-card families (intentional)

`features/conversations/references/reference-card.tsx` and
`features/collaboration/references/entity-reference-card.tsx` look similar and
are **deliberately not merged**. They render in different contexts (inside a
message thread vs. an inspector), cover different entity sets, and are typed
against their own domain's contracts. Merging them would couple two feature
modules through a shared type — a worse outcome than a similar-looking card.

---

## 6. Accessibility summary

Target: **WCAG 2.1 AA**.

- **Semantic HTML first.** Landmarks (`main`, `nav`, `aside`, `header`,
  `footer`), real `<button>`/`<a>` elements, `<ol>`/`<ul>` for sequences,
  `<dl>` for metadata, `<time datetime>` for every timestamp.
- **Labels.** Every icon-only control has an `aria-label`; every form control is
  bound through `Field`'s render-prop (`htmlFor` / `aria-describedby` /
  `aria-invalid`). Decorative icons are `aria-hidden`.
- **Status never by colour alone.** `StatusBadge` always renders dot + text.
- **Keyboard.** Full keyboard reachability; roving arrow-key navigation in
  `DropdownMenu`; Escape closes menus, the mobile nav drawer, and both
  slide-over panels, returning focus to the trigger.
- **Focus visibility.** A ring token, not the UA outline, applied uniformly.
- **Reduced motion** is handled at two layers: a global
  `@media (prefers-reduced-motion: reduce)` rule that neutralises every
  animation and transition, plus `MotionConfig reducedMotion="user"` for
  Framer. Components that animate content (streaming text, feed stagger) also
  branch on `useReducedMotion()` so the *content* appears whole rather than
  merely appearing instantly.
- **Live regions.** The conversation thread is a `role="log"`; result counts
  announce via `role="status"`; error text via `role="alert"`.

---

## 7. Performance summary

| Technique | Where |
| --- | --- |
| Route-level code splitting | Every workspace screen is a `dynamic()` import with its own loading fallback |
| Panel lazy-loading | Heavy side panels (task inspector, execution graph, conversation context panel, notification inspector) load on demand |
| Memoized rows | Every card/row rendered in a list is `memo()`-wrapped |
| Memoized derivations | Filtering/sorting/grouping live in `useMemo` hooks (`use-filtered-*`, `use-message-groups`) |
| Stable store selectors | Selectors return stable references; a shared `NO_ATTACHMENTS` constant avoids the `?? []` snapshot trap |
| Optimistic updates | Notification toggles and read-state settle instantly, then reconcile |

**Bundle:** 102 kB shared First Load JS; heaviest workspace routes ~185–204 kB.
41 static pages prerender; only genuinely dynamic routes (`[id]`, catch-all) are
server-rendered on demand.

**Hydration:** every date formatter pins locale **and** time zone (UTC) so the
server and client cannot disagree. `utils/format.ts` documents why. The single
intentional exception is the copyright year in the auth panel, marked
`suppressHydrationWarning`.

---

## 8. Integration points for Sprint 18

### The mechanical change

For each domain, per adapter:

1. Write `services/<domain>/http-adapter.ts` implementing the existing
   `<Domain>Adapter` interface.
2. Swap one line in `services/<domain>/<domain>-service.ts`.
3. Delete nothing — keep the mock adapter for tests and Storybook.

### Backend readiness per domain

| Domain | Backend status | Integration note |
| --- | --- | --- |
| **Auth** | Built (Sprint 1C) | Real endpoints exist. Session shape must match `Session`/`AuthUser`. |
| **Employees** | Built (Sprint 1D/1E) | Ownership chains already enforced server-side. |
| **Memory** | Built & frozen (Sprint 2) | `Memory` contract is exact: `memory_type ∈ {permanent, working, learned}`, `importance_score` 0.0–1.0, `GET /memories` filters + paginates. Everything else this workspace shows (titles, collections, tags, status, links) is **projection** and needs a decision before binding. |
| **Conversations** | Built (Sprint 5) | `Conversation {id, employee_id, title, status, created_at, updated_at}`, `status ∈ {active, archived}`; `Message {id, conversation_id, role, content, created_at}`, `role ∈ {user, assistant, system}`, immutable. Message *kinds*, attachments, approvals, artifacts, participants, pins and sharing are projection. |
| **Workflows** | Partial | Definitions align to planning models; the execution engine is not built. |
| **Tasks** | Partial | Seven of ten `TASK_STATES` are the backend's `LifecycleStatus`; `PLANNING`, `WAITING_APPROVAL`, `BLOCKED` have no counterpart yet. `taskStateFromLifecycle` is the compile-time seam that breaks the build if the backend vocabulary drifts. |
| **Dashboard** | Derived | Metrics aggregate other domains; no dedicated endpoint. |
| **Collaboration** | Not built | The platform emits notification *events* (`WorkflowNotificationEvent`), but there is no notification centre, activity log, comment, mention, follow or bookmark store. Entirely projection. |

### Where "projection" is marked

Every `services/<domain>/types.ts` labels each vocabulary **Backend contract** or
**Projection** in place, with the reason. Trust those comments over this table —
they sit next to the code and cannot drift from it.

### Switching on live data

- **Polling / subscriptions:** inside `features/<domain>/hooks/use-<domain>.ts`.
  Each file marks the spot.
- **Realtime:** no WebSocket code exists anywhere. When it arrives it belongs
  behind the adapter, surfacing through the same query keys.
- **Errors:** each domain exports a typed error (`TaskError`,
  `ConversationError`, `CollaborationError`, …) with a `code` union. HTTP
  adapters should map status codes onto those codes so existing UI error
  handling keeps working unchanged.

---

## 9. Known intentional mock implementations

Everything below is **deliberate** and should be replaced, not repaired.

| Area | What is mocked |
| --- | --- |
| All data | Eight `Mock*Adapter` classes over deterministic fixtures |
| Auth | Session in `localStorage`; deterministic triggers (`error@neuraevo.com` → invalid credentials, code `000000` → invalid code) |
| Conversation replies | Scripted per conversation, cycled by user-turn count. **No LLM.** The typing indicator and streaming reveal are animation over already-complete fixture text |
| Voice | A disabled mic with a tooltip. **No speech APIs** |
| Task execution | Nothing runs. Commands record a *request*; no step advances, no progress ticks |
| Workflow execution | Canvas describes a graph; it does not execute one |
| Approvals | Decisions update local state only; nothing is gated or unblocked |
| Attachments / artifacts | Metadata + preview text. Nothing uploads, downloads, or opens |
| Mentions / follows / bookmarks | UI state only; no notification is delivered |
| Search | Substring filtering. **No ranking, no embeddings, no pgvector** — the real engine's retrieval is the backend's |
| Notifications | Static; nothing arrives after load. No push, no email, no Slack/Teams |

### Mock storage keys

Clearing these resets to fixtures:

```
neuraevo.mock.session
neuraevo.mock.employees            neuraevo.mock.employees.activity
neuraevo.mock.workflows
neuraevo.mock.tasks                neuraevo.mock.tasks.approvals
neuraevo.mock.tasks.timelines
neuraevo.mock.conversations        neuraevo.mock.conversations.messages
neuraevo.mock.collaboration.notifications
neuraevo.mock.collaboration.approvals
```

Preference keys (`neuraevo.ui`, `neuraevo.tasks`, `neuraevo.memory`,
`neuraevo.employees`, `neuraevo.conversations`,
`neuraevo.conversations.composer`, `neuraevo.collaboration`,
`neuraevo.onboarding`) hold user settings, not mock data.

---

## 10. Release checklist

### Build & static analysis

- [x] TypeScript clean (`tsc --noEmit`, strict)
- [x] ESLint clean across `app`, `features`, `components`, `hooks`, `services`, `store`, `layouts`
- [x] Production build clean — 41 static pages
- [x] Bundle stable — 102 kB shared First Load JS
- [x] No unused exports
- [x] No dead code
- [x] No duplicate utilities
- [x] No duplicate components *(two reference-card families are intentional — §5)*

### Runtime

- [x] Zero console errors
- [x] Zero React warnings
- [x] Zero hydration warnings
- [x] Stable dynamic imports — all 20 carry a loading fallback
- [x] Stable loading / empty / error states

### Boundaries

- [x] Root error boundary (`app/error.tsx`)
- [x] Global error boundary (`app/global-error.tsx`) — survives a root-layout failure
- [x] Workspace error boundary (`app/workspace/error.tsx`) — keeps the shell navigable
- [x] Not-found handling (`app/not-found.tsx`) + in-shell catch-all
- [x] Loading boundaries (`app/loading.tsx`, `app/workspace/loading.tsx`)
- [x] Route guard (`AuthGuard`) on every `/workspace` route

### Quality

- [x] Responsive at 320 / 375 / 768 / 1024 / 1440 — no horizontal overflow
- [x] Keyboard navigation and focus visibility
- [x] ARIA correctness and screen-reader labels
- [x] Reduced-motion behaviour (CSS + Framer + per-component)
- [x] Theme consistency (light / dark)
- [x] Design-token consistency — zero hardcoded colours in feature code
- [x] Navigation and route consistency

### Explicitly out of scope for RC1

- [ ] Backend integration — Sprint 18
- [ ] Realtime transport
- [ ] LLM, speech, and provider SDKs
- [ ] Execution engines (task, workflow)
- [ ] Automated test suite

---

## 11. Verification

RC1 was verified by:

- `npx tsc --noEmit`
- `npx next lint` across all source directories
- `npx next build`
- Browser verification of every workspace: real interactions driven and asserted
  on resulting DOM/state, console errors captured by patching `console.error`
  in-page during interaction rather than trusting a buffered log
- Responsive verification at all five breakpoints
- Drawer behaviour verified on **both** sides of the `xl` breakpoint (floating
  drawer with scroll lock below; static column without it above)
