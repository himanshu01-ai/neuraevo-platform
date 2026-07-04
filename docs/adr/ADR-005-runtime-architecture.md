# ADR-005 — Runtime Architecture

Status: Accepted

## Context
A conversation turn touches many concerns: ownership validation, context
assembly, prompt building, LLM generation, and persistence/indexing. These must
be composed without leaking business logic into the HTTP layer or coupling the
steps together.

## Decision
A single runtime entry point (`ConversationRuntimeService.execute`) **coordinates
only**, delegating each concern to a dedicated, injected service in a fixed order:
context engine → prompt builder → orchestrator → memory persistence. The router
(`conversation_runtime`) is HTTP-only: it validates the request, delegates, and
maps domain/provider errors to status codes. Ownership is validated once, inside
the context engine's composed services; persistence runs only after a successful
generation.

## Consequences
- Each step is independently testable and swappable; the runtime service holds no
  session, repository, or business logic.
- Clear error boundaries: domain errors → 404/403, provider errors → 502/504,
  unexpected errors surface as 500; best-effort indexing failures never fail the
  turn.
- Adding steps (e.g. tool execution) is a coordination change in one place, not a
  rewrite of the pipeline.
- Trade-off: several small services instead of one large handler — accepted for
  testability and separation of concerns.

## Alternatives Considered
- **Business logic in the router** — rejected: untestable, violates layering,
  couples HTTP to domain.
- **One monolithic runtime service doing all steps** — rejected: large class,
  poor isolation, hard to evolve.
- **Event/queue-driven turn processing** — deferred: unnecessary complexity for
  the current synchronous request/response model.
