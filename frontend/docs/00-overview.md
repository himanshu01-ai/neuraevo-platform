# 00 · Overview & Design Architecture

## What we are building

NeuraEvo is a **Voice-First Personal AI Employee Platform**. The user delegates
complete work; the AI **plans**, **executes** across capabilities (Browser,
Python, Files, Email, Calendar, GitHub), asks for **approval** when needed, and
**remembers** through the approved architecture.

The frontend must make that feel like a **premium enterprise operating system** —
in the lineage of Apple, Linear, Notion, Raycast, Cursor, and Vercel. **Not a
chatbot.** The interface centers on _work and its state_ (tasks, workflows,
artifacts, approvals, health), not on a stream of chat bubbles.

## The one-sentence test

Every screen answers exactly one question:

| Screen        | Question                              |
| ------------- | ------------------------------------- |
| Home          | What is happening?                    |
| AI Workspace  | What is my AI Employee doing?         |
| Workflow      | How is my work progressing?           |
| Memory        | What does it know?                    |
| Dashboard     | Is my system healthy?                 |
| Settings      | How is my platform configured?        |

If a screen cannot answer its question in the first viewport, the design is wrong.

## Design architecture (how the layers fit)

```
                    ┌───────────────────────────────────────────┐
                    │  design-system/tokens  (TS source of truth)│
                    └───────────────┬───────────────────────────┘
                                    │ mirrored (color) / mapped (scale)
                 ┌──────────────────┴──────────────────┐
                 ▼                                      ▼
     styles/globals.css  (CSS vars,           tailwind.config.ts
     runtime theme :root/.dark)               (utility classes)
                 │                                      │
                 └──────────────────┬───────────────────┘
                                    ▼
                     components/ui (shadcn primitives, themed)
                                    ▼
                     components/patterns (StatusBadge, EmptyState, …)
                                    ▼
             features/<domain>  ◀── services/ + hooks/ + store/ + types/
                                    ▼
                     layouts/ (AppShell)  →  app/ (routes)
```

**Principle:** value flows one direction — tokens → theme → primitives →
patterns → features → routes. Nothing lower reaches upward. Nothing hardcodes a
color, size, radius, or duration that a token already defines.

## Design pillars

1. **Calm & premium** — restraint over decoration; hairline borders before
   shadows; one confident accent (NeuraEvo Violet), never a rainbow.
2. **Fast** — 14px enterprise baseline, dense but breathable; motion ≤ 320ms;
   perceived performance via skeletons and optimistic UI.
3. **Legible state** — a single canonical status vocabulary (from the backend)
   drives every badge, node, and health signal, with consistent tone→color.
4. **Trustworthy** — approvals, artifacts, and system health are first-class;
   the UI never hides what the AI is doing or about to do.
5. **Accessible by construction** — WCAG 2.2 AA, keyboard-first, reduced-motion
   honored globally, not bolted on.

## What Sprint 17.0 delivers

- Design tokens (`design-system/tokens/*`) + CSS-variable theme + Tailwind theme.
- Shared domain vocabulary (`types/domain.ts`) mirrored from the frozen backend.
- Complete production folder architecture with per-folder placement rules.
- Brand, motion, component, layout, responsive, accessibility guidelines.
- State-management, API-layer, and navigation architecture.
- Screen architecture with ASCII wireframes for all 13 screens.
- Developer implementation rules (the definition of done for future sprints).

## What Sprint 17.0 explicitly does NOT deliver

Business pages, backend logic, authentication, API integration, real workflows,
real dashboards, business components. Those belong to Sprint 17.1+.

## Document map

| # | Doc | Governs |
| - | --- | ------- |
| 01 | [Design System](01-design-system.md) | tokens, color, type, spacing, theming |
| 02 | [Brand](02-brand-guidelines.md) | logo, accent, icon/illustration/3D style |
| 03 | [Motion](03-motion-guidelines.md) | transitions, micro-interactions, reduced-motion |
| 04 | [Components](04-component-guidelines.md) | specs for every primitive |
| 05 | [Layout](05-layout-guidelines.md) | shell, nav, cards, dialogs, ⌘K |
| 06 | [Frontend Architecture](06-frontend-architecture.md) | folders, boundaries, imports |
| 07 | [Accessibility](07-accessibility-guidelines.md) | WCAG, keyboard, focus, contrast |
| 08 | [Developer Rules](08-developer-rules.md) | definition of done, do/don't |
| 09 | [State & API](09-state-and-api.md) | Zustand vs Query, services, errors |
| 10 | [Responsive](10-responsive-guidelines.md) | breakpoints, adaptive layouts |
| 11 | [Screen Architecture](11-screen-architecture.md) | wireframes + screen specs |
| 12 | [Navigation](12-navigation-architecture.md) | route map, IA, nav model |
| 13 | [Icon System](13-icon-system.md) | Lucide, sizes, stroke, nav/status icon maps |
| 14 | [Illustration](14-illustration-guidelines.md) | 3D/AI-Core, empty states, glass, gradients |
| 15 | [Sound](15-sound-guidelines.md) | opt-in audio cues, reduced-motion, volume |
| 16 | [Coding Rules](16-coding-rules.md) | naming, layers, TS/Tailwind, checklists |
| 17 | [Design Review](17-design-review-checklist.md) | production sign-off checklist |
