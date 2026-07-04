# Tool Execution Framework

## Purpose
Execute a single tool via a provider and return a provider-independent result.
Framework only — no concrete tool (Gmail/Calendar/Browser/…), HTTP, SDK, or
OAuth. Package: `app/services/tools/`.

## Responsibilities
- `ToolExecutionService.execute(request)` — delegate to the injected
  `ToolProvider` and return its `ToolExecutionResult` unchanged. Stateless;
  performs no planning, permissions, retries, or logging.
- `ToolProvider` (ABC) — the replaceable tool (`tool_name`, `description`,
  `validate`, `execute`). No concrete provider ships yet.
- DTOs: `ToolExecutionRequest` (non-empty `tool_name`, `arguments`/`metadata`
  default `{}`) and `ToolExecutionResult` (`success`, `output`, `error`,
  `execution_time_ms`; immutable via `frozen=True`).

## Dependencies
- Only its own `models` and `providers`. Imports no planner/permission/registry
  code — a leaf framework.

## Extension Points
- Implement `ToolProvider` per real tool; register instances in the Tool Registry
  and wire the active provider via `get_tool_provider`. No orchestrator/runtime
  changes are needed to add tools.

## Execution Flow
```
execute(ToolExecutionRequest) → ToolProvider.execute(request) → ToolExecutionResult
```
No provider/SDK object crosses the service boundary; results are plain DTOs.
