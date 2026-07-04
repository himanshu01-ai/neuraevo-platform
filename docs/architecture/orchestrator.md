# AI Orchestrator

## Purpose
`AIOrchestratorService` (`app/services/orchestrator/`) is the coordination point
for (a) the conversation-generation path (`run`) and (b) the Agent Execution Core
(`execute_agent_request`). It coordinates only — it generates no plan, builds no
prompt content, checks no permission, and executes no tool itself.

## Responsibilities
- `run(context)` — build a `PromptPackage`, resolve the active conversation
  provider, invoke it, and wrap the reply in a provider-agnostic `AIResponse`.
- `execute_agent_request(user_request)` — coordinate plan → per-step
  permission-gated tool execution, preserving plan order.
- No retries, no exception wrapping, no mutation, no caching; holds no session.

## Dependencies (constructor-injected)
- `RuntimePromptBuilderService`, `ConversationProviderFactory` — the `run` path.
- `PlannerService`, `PermissionService`, `ToolRegistry`, `ToolExecutionService`
  — the agent path. These are **optional** (a provider seam may be unfulfilled);
  the `run` path never uses them, so the runtime DI chain always resolves.

## Extension Points
- New conversation providers arrive via `ConversationProviderFactory` — no change here.
- New tools arrive via `ToolRegistry`/`ToolProvider` — no change here.
- Guard: if the agent collaborators are unconfigured, `execute_agent_request`
  fails fast with a clear `RuntimeError` (never an `AttributeError`).

## Execution Flow (agent path)
```
execute_agent_request(user_request)
  guard: any of {planner, permissions, tool_registry, tool_execution} is None → RuntimeError
  plan = PlannerService.create_plan(user_request)
  for step in plan.steps:                        # plan order preserved
      ToolRegistry.get_tool(step.tool_name)       # KeyError if unknown (no fallback)
      result = PermissionService.check_permission(PermissionRequest(...))
      if not result.approved or result.requires_user_confirmation:
          return result                           # HALT, remaining steps skipped
      results.append(ToolExecutionService.execute(ToolExecutionRequest(...)))
  return results                                  # list[ToolExecutionResult], in order
```
