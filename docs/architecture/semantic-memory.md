# Semantic Memory

## Purpose
Give conversations long-term recall: index persisted messages as vectors and
retrieve the most semantically similar memories for a new user input.
PostgreSQL is the source of truth; the vector store is only a searchable index.
Packages: `app/services/memory/` (retrieval + persistence).

## Responsibilities
- **Indexing** (`MemoryPersistenceService`): after the authoritative DB commit of
  a turn, best-effort generate an embedding and `upsert_vector` the memory.
  Failures never roll back or lose the saved memory.
- **Retrieval** (`MemoryRetrievalService.retrieve_semantic`): embed the query →
  `search_vectors` for the top-K memory ids (ranked) → load those rows from
  PostgreSQL → return them in the exact vector-search order. Vector-store payload
  text is never trusted.
- **Merge** (`AIContextEngineService`): recent chronological history first, then
  semantic memories appended, de-duplicated by `message.id`, order preserved.

## Dependencies (constructor-injected)
- `EmbeddingService` (query/memory → vector), `VectorStoreService` (index +
  search), `MessageRepository` (authoritative rows). Embedding service is
  optional until a provider exists; retrieval requires it, so it fails clearly
  when unavailable while conversation-history retrieval keeps working.

## Extension Points
- Provide an embedding provider (`get_embedding_provider`) and a vector-store
  provider to activate the semantic path; no orchestrator/prompt changes.
- Prompt-time windowing of `retrieved_history` lives in the prompt builder
  (`MAX_RETRIEVED_HISTORY_MESSAGES`), independent of retrieval.

## Execution Flow
```
Index:   persist(turn) → DB commit → embed(assistant text) → upsert_vector(id, vec, payload)
Retrieve: retrieve_semantic(query) → embed(query) → search_vectors → get_by_ids(ranked) → ranked rows
Merge:   build_context → retrieve() + retrieve_semantic() → dedupe by id → retrieved_history
```
