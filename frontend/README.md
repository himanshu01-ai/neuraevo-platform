# NeuraEvo — Web Frontend

The web client for **NeuraEvo AI Employee**. Not a chatbot — an enterprise
operating system for delegating, watching, and approving real work done by an
autonomous AI employee.

> **Sprint 17.0 — Design System & Product UX Foundation.**
> This sprint establishes the design language, architecture, and guidelines that
> govern **every future frontend sprint**. It contains foundation only:
> tokens, configuration, structure, and specifications. **No product pages, no
> business logic, no API integration, no authentication.**

## Stack (locked)

Next.js 15 · React 19 · TypeScript · Tailwind CSS · shadcn/ui · TanStack Query ·
Zustand · React Hook Form · Zod · Lucide · Framer Motion · React Three Fiber.

## Where things live

| Folder            | Purpose                                                        |
| ----------------- | ------------------------------------------------------------- |
| `app/`            | Next.js App Router — routes, layouts, server components       |
| `components/`     | reusable domain-agnostic UI (`ui/`, `patterns/`, `brand/`)    |
| `features/`       | vertical domain slices (workspace, tasks, workflow, …)        |
| `layouts/`        | app-shell chrome (sidebar, top nav, mobile nav)               |
| `hooks/`          | cross-cutting React hooks                                     |
| `services/`       | API layer — the only code that talks to the backend           |
| `store/`          | Zustand client/UI state                                       |
| `types/`          | global shared types (`domain.ts` mirrors the backend)         |
| `styles/`         | `globals.css` — the CSS-variable theme contract               |
| `providers/`      | root React context providers                                  |
| `lib/`            | framework-aware shared infra (`cn`, query client, env)        |
| `utils/`          | pure dependency-free helpers                                  |
| `design-system/`  | design tokens (source of truth for the visual language)       |
| `assets/`         | brand + static media                                          |
| `docs/`           | the guidelines below                                          |

## Documentation

Read in order; `docs/00-overview.md` is the map.

1. [00 · Overview & Design Architecture](docs/00-overview.md)
2. [01 · Design System](docs/01-design-system.md)
3. [02 · Brand Guidelines](docs/02-brand-guidelines.md)
4. [03 · Motion Guidelines](docs/03-motion-guidelines.md)
5. [04 · Component Guidelines](docs/04-component-guidelines.md)
6. [05 · Layout Guidelines](docs/05-layout-guidelines.md)
7. [06 · Frontend Architecture](docs/06-frontend-architecture.md)
8. [07 · Accessibility Guidelines](docs/07-accessibility-guidelines.md)
9. [08 · Developer Rules](docs/08-developer-rules.md)
10. [09 · State & API Architecture](docs/09-state-and-api.md)
11. [10 · Responsive Guidelines](docs/10-responsive-guidelines.md)
12. [11 · Screen Architecture & Wireframes](docs/11-screen-architecture.md)
13. [12 · Navigation Architecture](docs/12-navigation-architecture.md)
14. [13 · Icon System](docs/13-icon-system.md)
15. [14 · Illustration Guidelines](docs/14-illustration-guidelines.md)
16. [15 · Sound Guidelines](docs/15-sound-guidelines.md)
17. [16 · Frontend Coding Rules](docs/16-coding-rules.md)
18. [17 · Design Review Checklist](docs/17-design-review-checklist.md)

## Getting started (future sprints)

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run typecheck  # tsc --noEmit
npm run lint
```

> No `node_modules` is committed. The foundation is verified by structure and
> self-contained types; a Node toolchain is required to install and run.
