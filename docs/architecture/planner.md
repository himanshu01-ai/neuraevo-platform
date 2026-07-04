# Planner Framework

## Purpose
Turn a natural-language user request into an immutable, ordered `ExecutionPlan`
describing which tool steps *would* run. Planning only — it executes nothing.
Package: `app/services/planner/`.

## Responsibilities
- `PlannerService.create_plan(user_request)` — delegate to the injected
  `PlannerProvider` and return its `ExecutionPlan` unchanged. Stateless.
- `PlannerProvider` (ABC) — the replaceable planning strategy (`name`,
  `create_plan`). No concrete provider ships yet.
- DTOs (`PlanningStep`, `ExecutionPlan`) are immutable (`frozen=True`) and
  provider-independent; `PlanningStep` requires a non-empty `tool_name` and
  `description`, with `arguments` defaulting to `{}`.

## Dependencies
- Only its own `models` and `providers`. It imports **no** tool execution,
  permission, registry, or runtime code — it is a leaf framework.

## Extension Points
- Implement `PlannerProvider` (e.g. an LLM-backed planner) and register it in the
  composition root (`get_planner_provider`). No consumer changes required.

## Execution Flow
```
create_plan(user_request) → PlannerProvider.create_plan(user_request) → ExecutionPlan(steps=[PlanningStep, ...])
```
The orchestrator consumes the plan; the planner never sees the registry,
permission service, or executor.
