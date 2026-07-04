# ADR-002 — Semantic Memory Architecture

Status: Accepted

## Context
Conversations need long-term recall beyond the recent message window. Vector
databases enable similarity search, but they are an index, not a system of
record, and their stored payloads can drift or be tampered with.

## Decision
**PostgreSQL is the source of truth; Qdrant is only a searchable index.**
- Indexing is **best-effort and happens after** the authoritative DB commit
  (`MemoryPersistenceService`); an embedding/upsert failure never rolls back or
  loses the saved memory.
- Retrieval returns **ids + scores** from the vector store, then loads the real
  rows from PostgreSQL preserving vector rank; vector-store payload text is never
  trusted (`MemoryRetrievalService.retrieve_semantic`).
- Embeddings and vector store are separate leaf frameworks coordinated by Memory;
  the AI Context Engine merges recent + semantic history, de-duplicated by id.

## Consequences
- Durability and correctness are guaranteed by PostgreSQL; the index can be
  rebuilt without data loss.
- Semantic memory degrades gracefully: without an embedding provider, indexing is
  skipped and conversation-history retrieval still works.
- Extra read (vector search → DB load) per retrieval; acceptable and batched.

## Alternatives Considered
- **Vector DB as source of truth** — rejected: weaker durability/consistency,
  untrusted payloads, harder migrations.
- **Store memory text only in Qdrant payloads** — rejected: duplication and
  tamper risk; violates single source of truth.
- **Synchronous, transactional indexing** — rejected: a vector-store outage would
  fail user turns and could lose the DB write.
