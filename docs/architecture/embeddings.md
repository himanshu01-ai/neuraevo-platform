# Embeddings

## Purpose
Turn text into an embedding vector via a replaceable provider. Framework only —
no concrete provider, SDK, API key, or HTTP call. Package:
`app/services/embeddings/`.

## Responsibilities
- `EmbeddingService.generate_embedding(text)` — delegate to the injected
  `EmbeddingProvider` and return the vector unchanged. Stateless; no caching,
  batching, retries, or persistence.
- `EmbeddingProvider` (ABC) — the replaceable strategy (`name`,
  `generate_embedding`). No concrete provider ships yet.

## Dependencies
- Only its own `providers`. Imports no vector-store/memory/runtime code — a leaf
  framework.

## Extension Points
- Implement `EmbeddingProvider` (OpenAI/Voyage/Jina/…) and register it in
  `get_embedding_provider`. The composition root's `get_optional_embedding_service`
  yields `None` until then, so memory persistence/retrieval degrade gracefully
  rather than breaking the runtime DI chain.

## Execution Flow
```
generate_embedding(text) → EmbeddingProvider.generate_embedding(text) → list[float]
```
Consumed by Semantic Memory for both memory indexing and query retrieval.
