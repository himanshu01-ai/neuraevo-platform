# ADR-001 — Constructor Dependency Injection

Status: Accepted

## Context
The backend is layered (routers → services → repositories) with many
collaborating services. We need testable, swappable wiring without hidden global
state, and a single place that knows how objects are built.

## Decision
Every service receives its collaborators through its **constructor**. All
construction happens only in the composition root (`app/core/dependencies.py`)
using FastAPI `Depends`. Services never instantiate other services, providers, or
repositories internally. Provider seams that are not yet implemented raise
`NotImplementedError` in the composition root; resilient `get_optional_*_service`
assemblers return `None` so runtime-critical DI chains still resolve.

## Consequences
- Unit tests inject mocks directly — no patching of globals; fast, isolated tests.
- Swapping an implementation is a one-line change in the composition root.
- No service locator, no singletons (except the config `settings`), no runtime
  service creation.
- Trade-off: the composition root is large (~800 lines) and centralizes wiring
  knowledge; accepted for now (kept as one cohesive file, not split).

## Alternatives Considered
- **Service locator / global registry** — rejected: hidden dependencies, harder
  tests, unclear ownership.
- **Framework DI container (e.g. `dependency-injector`)** — rejected: extra
  dependency and indirection; FastAPI `Depends` already suffices.
- **Module-level singletons per service** — rejected: global state, poor test
  isolation, request-scoping problems.
