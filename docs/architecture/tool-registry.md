# Tool Registry

## Purpose
Maintain the catalogue of registered `ToolProvider` instances so an orchestrator
can ask "what tools exist?". It stores providers and nothing else. Package:
`app/services/tools/registry/`.

## Responsibilities
- `register(provider)` — add a provider; raise `ValueError` on a duplicate
  `tool_name`. The provider object is stored unchanged (the only mutation).
- `list_tools()` — return plain `[{"tool_name", "description"}]` dicts; never
  expose provider objects.
- `get_tool(tool_name)` — return the provider, or raise `KeyError`.
- `has_tool(tool_name)` — return a bool.
- Never executes, validates, permissions, plans, caches, or imports SDKs.

## Dependencies
- Only `ToolProvider` (the abstract base). Holds a single `self.providers` list.

## Extension Points
- Supply providers at construction (composition root `get_tool_providers` →
  `get_tool_registry`); a later sprint returns the real provider list there.

## Execution Flow
```
ToolRegistry([...providers])           # unique tool_name enforced
  .get_tool("send_email")   → ToolProvider | KeyError
  .list_tools()             → [{"tool_name": ..., "description": ...}, ...]
```
Lookups are O(n) list scans — appropriate for the expected number of tools.
