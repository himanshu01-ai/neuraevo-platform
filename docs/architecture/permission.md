# Permission Framework

## Purpose
Decide whether a tool call is permitted, before any execution. Framework only —
no concrete policy, user-approval flow, or execution. Package:
`app/services/permissions/`.

## Responsibilities
- `PermissionService.check_permission(request)` — delegate to the injected
  `PermissionProvider` and return its `PermissionResult` unchanged. Stateless.
- `PermissionProvider` (ABC) — the replaceable policy (`name`,
  `check_permission`). No concrete provider ships yet.
- DTOs: `PermissionRequest` (non-empty `tool_name`, `arguments`/`metadata`
  default `{}`) and `PermissionResult` (`approved`, `reason`,
  `requires_user_confirmation`; immutable via `frozen=True`).

## Dependencies
- Only its own `models` and `providers`. Imports no tool/registry/planner/runtime
  code — a leaf framework.

## Extension Points
- Implement `PermissionProvider` (allow-list, per-user policy, confirmation
  rules) and register it in `get_permission_provider`. No consumer changes.

## Execution Flow
```
check_permission(PermissionRequest) → PermissionProvider.check_permission(...) → PermissionResult
```
Deny-by-default is expressed by the caller: the orchestrator halts and returns
the `PermissionResult` when `approved` is false OR `requires_user_confirmation`
is true, and never executes subsequent steps.
