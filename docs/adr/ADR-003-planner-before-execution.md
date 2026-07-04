# ADR-003 — Planner Before Execution

Status: Accepted

## Context
Agent requests may require multiple tool calls. Executing tools directly from a
model's free-form output is opaque and unsafe: there is no point at which the
intended actions can be inspected, permission-gated, or ordered deterministically.

## Decision
Separate **planning** from **execution**. A `PlannerService` first produces an
immutable, ordered `ExecutionPlan` (`PlanningStep`s). The orchestrator then walks
the plan in order and, **per step**, resolves the tool (registry), checks
permission, and only then executes. If a step is not approved or requires user
confirmation, execution halts immediately and the `PermissionResult` is returned;
remaining steps are not run.

## Consequences
- The full intended action sequence is inspectable and gate-able before anything
  runs — a clean seam for permissions, confirmation, and (future) auditing.
- Deterministic, planner-defined order; failures/denials halt cleanly with later
  steps skipped.
- Planner, permission, registry, and executor are independent leaf frameworks;
  the orchestrator is the only coordinator.
- Trade-off: two phases add a step versus direct execution — accepted for safety
  and inspectability.

## Alternatives Considered
- **Direct tool execution from model output** — rejected: no inspection or
  gating point; unsafe and non-deterministic.
- **Permission checks inside the planner or executor** — rejected: violates
  single-responsibility; the gate belongs at coordination time.
- **Whole-plan approval before any execution** — deferred: per-step gating is
  stricter and supports mid-plan confirmation; can be layered later.
