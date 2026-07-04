# Vector Store

## Purpose
A vendor-neutral interface to a vector database (Qdrant), used to index memory
vectors and run similarity search. Infrastructure only — no embedding
generation. Package: `app/services/vector_store/`.

## Responsibilities
- `VectorStoreService` — stateless delegator over the injected
  `VectorStoreProvider`: `health_check`, `collection_exists`,
  `create_collection`, `delete_collection`, `upsert_vector`, `search_vectors`.
- `VectorStoreProvider` (ABC) — the replaceable backend contract.
- `QdrantProvider` — the concrete backend. The `qdrant_client` SDK is imported
  **lazily** (client built on first use / injectable for tests), so importing
  the module never requires the package or a live server. Search results are
  converted to plain `(point_id, score)` tuples — **no SDK object escapes** the
  provider. Errors are wrapped as `VectorStoreError`.

## Dependencies
- Connection settings (`QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_TIMEOUT_SECONDS`)
  read in the composition root; `qdrant-client` (declared, lazily imported).

## Extension Points
- Swap the backend by implementing `VectorStoreProvider` and changing one line in
  `get_vector_store_provider`; no service/consumer changes.

## Execution Flow
```
upsert_vector(collection, id, vector, payload) → provider → client.upsert
search_vectors(collection, query_vector, limit) → provider → client.search → [(id, score), ...]
```
