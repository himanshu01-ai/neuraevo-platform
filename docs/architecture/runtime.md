# Conversation Runtime

## Purpose
The single runtime entry point for AI conversation execution. Exposed over HTTP
by the Conversation Runtime API (`POST /api/v1/conversations/{conversation_id}/runtime`)
and implemented by `ConversationRuntimeService` (`app/services/runtime/`).

## Responsibilities
- Coordinate one conversation turn end-to-end; own no business logic itself.
- Sequence: assemble context → build prompt → generate reply → persist the turn.
- Return a provider-agnostic `AIResponse`.
- It holds **no session and no repository**; the collaborators it calls own those.

## Dependencies (constructor-injected)
- `AIContextEngineService` — assembles `RuntimeAIContext` (ownership validated here).
- `RuntimePromptBuilderService` — builds the `PromptPackage` (telemetry/coordination visibility).
- `AIOrchestratorService` — generates the reply.
- `MemoryPersistenceService` — persists the completed turn (and best-effort indexes it).

## Extension Points
- Swap any collaborator via the composition root (`core/dependencies.py`); the
  runtime service is unchanged.
- The router maps domain errors (`Employee/Blueprint/ConversationError`) to
  404/403 and provider errors to 502/504 — extend the map, not the service.

## Execution Flow
```
POST /conversations/{id}/runtime
  → ConversationRuntimeService.execute(owner, employee_id, conversation_id, user_input)
      1. context = AIContextEngineService.build_context(...)      # ownership enforced
      2. package = RuntimePromptBuilderService.build(context)     # telemetry
      3. response = AIOrchestratorService.run(context)            # generation
      4. MemoryPersistenceService.persist(..., response)          # DB write, then best-effort index
      → return AIResponse
```
Ownership is validated exactly once (inside the context engine's collaborators);
persistence runs only after a successful generation and never rolls the turn back
for an indexing failure.
