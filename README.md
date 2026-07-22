# NeuraEvo

**A voice-first personal AI employee platform.** Users create personalized AI
employees through an interview-driven onboarding flow, then talk to them, delegate
tasks and workflows, give them memory, and collaborate around them — by voice or
text.

> **Status:** feature-complete; preparing for Release Candidate (RC1). All twelve
> platform domains below are implemented, tested, and backward-compatible.

---

## Platform domains

| Domain | What it does |
|---|---|
| Authentication | Registration, login, JWT access/refresh, email verification, password reset |
| AI Employees | Employee lifecycle, configuration, capabilities, permissions, assignments, activity |
| Blueprints | The employee's persisted definition, AI-assisted generation, immutable version history & restore |
| Interview System | Questions, answers, sessions, and per-session execution that shape an employee |
| Tasks | Described work launched on the workflow runtime |
| Workflows | Authored workflows and recorded executions |
| Memory | The Memory Engine — create, retrieve, update, delete, filter, paginate, stats |
| Conversation | Employee-scoped and user-scoped conversations; text and voice turns |
| Voice Experience | The voice runtime and transcript surface |
| Collaboration | Participants, secure share links, the activity timeline, the notification inbox |
| Platform Integration | Cross-domain timeline + inbox, conversation→task orchestration, memory workspace |
| API / Security / Performance hardening | One error contract, request correlation, security headers, rate limiting, N+1-free reads, tuned pooling |

---

## Architecture

A strict, layered backend and a feature-sliced frontend. Boundaries are enforced,
not just documented (see [`CLAUDE.md`](CLAUDE.md) for the full rules).

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend — Next.js 15 (App Router), TypeScript, TanStack    │
│  Query, feature-sliced modules, backend/mock service adapters│
└───────────────────────────────┬─────────────────────────────┘
                                 │  HTTP  /api/v1
┌───────────────────────────────▼─────────────────────────────┐
│  API layer      routers: request validation, DI, HTTP,       │
│                 Swagger — no business logic                  │
│  Service layer  ownership, business rules, workflow & AI      │
│                 orchestration, transactions, versioning      │
│  Repository     persistence only: queries, CRUD, flush        │
│  Models         SQLAlchemy ORM (PostgreSQL + pgvector)        │
└──────────────────────────────────────────────────────────────┘
```

- **Routers never contain business logic.** **Repositories never make business
  decisions.** **Services are the only place business decisions live.**
- **AI providers are isolated** — routers, repositories, and models never call a
  provider directly; prompt construction is centralized and providers are
  replaceable.

---

## Tech stack

- **Backend:** FastAPI, Python 3.11+, SQLAlchemy 2, Alembic, PostgreSQL + pgvector,
  Qdrant (vector store, optional), Anthropic Claude, PyJWT, bcrypt, Playwright
  (optional Browser capability).
- **Frontend:** Next.js 15, TypeScript, TanStack Query, React Hook Form + Zod,
  Framer Motion, Tailwind-based design system, Vitest.
- **Infrastructure:** Docker, Nginx, Render; Prometheus scrape config under
  `infrastructure/monitoring/`.

---

## Repository layout

```
NeuraEvo/
├── backend/                 FastAPI application
│   ├── app/
│   │   ├── api/v1/          Routers (HTTP layer)
│   │   ├── core/            Config, database, security, middleware, DI
│   │   ├── models/          SQLAlchemy ORM models
│   │   ├── repositories/    Persistence-only data access
│   │   ├── schemas/         Pydantic request/response schemas
│   │   ├── services/        Business logic, orchestration, AI, runtime
│   │   └── utils/           Shared helpers, constants, logging
│   ├── alembic/             Database migrations
│   ├── tests/               Test suite (stdlib unittest)
│   └── requirements.txt
├── frontend/                Next.js app (see frontend/README.md)
│   ├── app/                 App Router routes
│   ├── features/            Feature-sliced modules
│   ├── services/            Backend/mock service adapters
│   └── docs/                Frontend design & engineering guides
├── docs/                    Architecture, ADRs, deployment
└── infrastructure/          Docker, Nginx, Render, monitoring
```

---

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 18.18+ (Next.js 15)
- PostgreSQL 15+ with the `pgvector` extension (for a live backend)

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\pip   |   macOS/Linux: .venv/bin/pip
.venv/Scripts/pip install -r requirements.txt

# Configure the environment (see backend/.env.example for every setting)
cp .env.example .env
# then edit .env — at minimum set DATABASE_URL, JWT_SECRET_KEY, ANTHROPIC_API_KEY

# Run the API (serves http://localhost:8000, docs at /docs)
.venv/Scripts/python -m uvicorn app.main:app --reload
```

Run the test suite (this project uses stdlib `unittest`, not pytest):

```bash
cd backend
PYTHONPATH=. .venv/Scripts/python -m unittest discover -s tests -p "test_*.py"
```

Interactive API docs are served at `http://localhost:8000/docs` (Swagger UI) and
`http://localhost:8000/redoc`; the OpenAPI schema is at
`http://localhost:8000/api/v1/openapi.json`.

### Frontend

```bash
cd frontend
npm install

# Configure the environment (see frontend/.env.example for every variable)
cp .env.example .env.local
# NEXT_PUBLIC_API_BASE_URL should point at the backend, e.g.
# http://localhost:8000/api/v1

npm run dev        # http://localhost:3000
```

Other frontend scripts:

```bash
npm run build      # production build
npm run lint       # ESLint (next lint)
npm run typecheck  # tsc --noEmit
npm run test       # Vitest
```

Each domain's frontend service can run against the live backend (default) or an
offline **mock** adapter via a `NEXT_PUBLIC_*_ADAPTER=mock` switch — see
`frontend/.env.example`, useful for UI-only work without a running API.

---

## Configuration

- **Backend:** every setting is defined in
  [`backend/app/core/config.py`](backend/app/core/config.py) and documented in
  [`backend/.env.example`](backend/.env.example). The app fails fast on an unsafe
  production config (wildcard CORS or the default JWT secret outside development).
- **Frontend:** public variables are validated by
  [`frontend/lib/env.ts`](frontend/lib/env.ts) (Zod) and documented in
  [`frontend/.env.example`](frontend/.env.example). Only `NEXT_PUBLIC_*` values —
  they are inlined into the client bundle and must never carry secrets.

---

## Documentation

- [`CLAUDE.md`](CLAUDE.md) — architecture rules and layer boundaries
- [`docs/deployment.md`](docs/deployment.md) — runtime dependencies & the Browser capability
- [`docs/architecture/`](docs/architecture/) and [`docs/adr/`](docs/adr/) — architecture & decision records
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — roadmap
- [`frontend/docs/`](frontend/docs/) — frontend design system, accessibility, state & API guides

---

## Testing at a glance

| Suite | Command |
|---|---|
| Backend | `cd backend && PYTHONPATH=. .venv/Scripts/python -m unittest discover -s tests -p "test_*.py"` |
| Frontend unit | `cd frontend && npm run test` |
| Types | `cd frontend && npm run typecheck` |
| Lint | `cd frontend && npm run lint` |
