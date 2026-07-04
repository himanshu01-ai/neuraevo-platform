# ADR-004 — Provider Pattern

Status: Accepted

## Context
Several capabilities depend on external or swappable implementations: embeddings,
vector store, conversation LLM, tools, permissions, planning. Vendor SDKs must not
leak into services, and the system must build and be tested without any concrete
provider present.

## Decision
Each capability is a package with the same shape:
`models.py` (immutable, provider-independent DTOs) + `providers/base.py`
(an abstract `*Provider`) + a stateless `*Service` delegator + package exports.
Concrete providers implement the ABC and own **all** vendor-specific code (SDKs
imported lazily). The active provider is chosen only in the composition root; an
unimplemented provider seam raises `NotImplementedError` until fulfilled.

## Consequences
- Uniform, predictable structure across `embeddings`, `vector_store`, `tools`,
  `permissions`, `planner` — easy to learn and extend.
- Services depend on abstractions, not vendors (Dependency Inversion); no SDK
  object crosses a service boundary.
- The system boots and is fully unit-testable with mocks before any provider
  exists; adding a provider is localized and requires no consumer changes.
- Trade-off: some boilerplate per capability and currently-inert seams — accepted
  for isolation and testability.

## Alternatives Considered
- **Direct SDK calls inside services** — rejected: vendor lock-in, untestable
  without credentials/network, leaks provider types.
- **A single generic provider interface for everything** — rejected: capabilities
  have different contracts; a shared interface would be lowest-common-denominator.
- **Concrete implementations up front** — rejected: violates framework-first
  sequencing and couples milestones to external accounts.
