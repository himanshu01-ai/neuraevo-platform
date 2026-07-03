"""Unit tests for the Memory Retrieval Service (Sprint 9.1; 10.4 semantic).

Every collaborator is mocked (message repository, embedding service, vector
store), so no database, embedding API, or Qdrant is touched. Two groups:

* Sprint 9.1 ``retrieve`` — conversation history, unchanged.
* Sprint 10.4 ``retrieve_semantic`` — embed the query once, search the vector
  store once, load the ranked ids from PostgreSQL once, and return the real
  rows in the exact vector-search order (never Qdrant payloads/SDK objects).

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_memory_retrieval_service
"""

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.memory.memory_retrieval_service import (
    MemoryRetrievalService,
)

_LOGGER = "app.services.memory.memory_retrieval_service"


class MemoryRetrievalServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.owner = MagicMock(name="User")
        self.owner.id = uuid.uuid4()
        self.employee_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()

        self.stored_messages = [
            MagicMock(name="message_1"),
            MagicMock(name="message_2"),
        ]
        self.messages = MagicMock(name="MessageRepository")
        self.messages.list_messages.return_value = self.stored_messages

        self.embeddings = MagicMock(name="EmbeddingService")
        self.query_vector = [0.1, -0.2, 0.3]
        self.embeddings.generate_embedding.return_value = self.query_vector
        self.vector_store = MagicMock(name="VectorStoreService")

        self.service = MemoryRetrievalService(
            self.messages, self.embeddings, self.vector_store
        )

    def _retrieve(self):
        return self.service.retrieve(
            self.owner, self.employee_id, self.conversation_id
        )

    # =================================================================
    # Sprint 9.1 — conversation history (unchanged)
    # =================================================================
    def test_repository_called_exactly_once(self):
        self._retrieve()
        self.messages.list_messages.assert_called_once()

    def test_correct_conversation_id_passed(self):
        self._retrieve()
        self.messages.list_messages.assert_called_once_with(
            self.conversation_id
        )

    def test_correct_owner_and_employee_id_used(self):
        with self.assertLogs(_LOGGER, level="INFO") as captured:
            self._retrieve()
        output = "\n".join(captured.output)
        self.assertIn(str(self.owner.id), output)
        self.assertIn(str(self.employee_id), output)
        self.assertIn(str(self.conversation_id), output)

    def test_returned_messages_unchanged(self):
        result = self._retrieve()
        self.assertIs(result, self.stored_messages)

    def test_empty_conversation_returns_empty_list(self):
        self.messages.list_messages.return_value = []
        result = self._retrieve()
        self.assertEqual(result, [])

    def test_repository_exception_propagates(self):
        self.messages.list_messages.side_effect = RuntimeError("db down")
        with self.assertRaises(RuntimeError):
            self._retrieve()

    def test_no_write_calls_on_repository(self):
        self._retrieve()
        self.messages.create_message.assert_not_called()
        self.messages.delete_message.assert_not_called()

    def test_retrieve_does_not_touch_semantic_collaborators(self):
        self._retrieve()
        self.embeddings.generate_embedding.assert_not_called()
        self.vector_store.search_vectors.assert_not_called()

    # =================================================================
    # statelessness / DI
    # =================================================================
    def test_stateless_only_injected_collaborators(self):
        self.assertEqual(
            set(vars(self.service)),
            {"messages", "embeddings", "vector_store"},
        )

    def test_constructor_uses_injected_dependencies(self):
        self.assertIs(self.service.messages, self.messages)
        self.assertIs(self.service.embeddings, self.embeddings)
        self.assertIs(self.service.vector_store, self.vector_store)

    def test_di_provider_wires_collaborators_without_manual_instantiation(self):
        from app.core.dependencies import get_memory_retrieval_service
        from app.repositories.message_repository import MessageRepository

        session = MagicMock(name="Session")
        embeddings = MagicMock(name="EmbeddingService")
        vector_store = MagicMock(name="VectorStoreService")
        service = get_memory_retrieval_service(session, embeddings, vector_store)
        self.assertIsInstance(service, MemoryRetrievalService)
        self.assertIsInstance(service.messages, MessageRepository)
        self.assertIs(service.embeddings, embeddings)
        self.assertIs(service.vector_store, vector_store)

    # =================================================================
    # Sprint 10.4 — semantic retrieval
    # =================================================================
    def _rows(self, ids):
        # Real-ish PostgreSQL rows: an id plus content (never from Qdrant).
        return [
            SimpleNamespace(id=mid, content=f"content-{i}")
            for i, mid in enumerate(ids)
        ]

    def _configure_semantic(self, ranked, rows):
        self.vector_store.search_vectors.return_value = ranked
        self.messages.get_by_ids.return_value = rows

    def test_semantic_embeds_query_exactly_once(self):
        mid = uuid.uuid4()
        self._configure_semantic([(str(mid), 0.9)], self._rows([mid]))
        self.service.retrieve_semantic("what did we discuss?")
        self.embeddings.generate_embedding.assert_called_once_with(
            "what did we discuss?"
        )

    def test_semantic_searches_vector_store_exactly_once(self):
        mid = uuid.uuid4()
        self._configure_semantic([(str(mid), 0.9)], self._rows([mid]))
        self.service.retrieve_semantic("q", limit=5)
        self.vector_store.search_vectors.assert_called_once_with(
            "memories", self.query_vector, 5
        )

    def test_semantic_loads_repository_exactly_once(self):
        ids = [uuid.uuid4(), uuid.uuid4()]
        self._configure_semantic(
            [(str(ids[0]), 0.9), (str(ids[1]), 0.5)], self._rows(ids)
        )
        self.service.retrieve_semantic("q")
        self.assertEqual(self.messages.get_by_ids.call_count, 1)

    def test_semantic_preserves_vector_ranking_exactly(self):
        # Qdrant returns C, A, B; result must be C, A, B (not id/DB order).
        c, a, b = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        ranked = [(str(c), 0.99), (str(a), 0.80), (str(b), 0.10)]
        # Repository returns rows in a DIFFERENT (e.g. pk/DB) order: A, B, C.
        rows = [
            SimpleNamespace(id=a, content="A"),
            SimpleNamespace(id=b, content="B"),
            SimpleNamespace(id=c, content="C"),
        ]
        self._configure_semantic(ranked, rows)
        result = self.service.retrieve_semantic("q")
        self.assertEqual([r.id for r in result], [c, a, b])
        self.assertEqual([r.content for r in result], ["C", "A", "B"])

    def test_semantic_loads_by_the_ranked_ids(self):
        ids = [uuid.uuid4(), uuid.uuid4()]
        self._configure_semantic(
            [(str(ids[0]), 0.9), (str(ids[1]), 0.4)], self._rows(ids)
        )
        self.service.retrieve_semantic("q")
        passed_ids = list(self.messages.get_by_ids.call_args.args[0])
        self.assertEqual(passed_ids, ids)

    def test_semantic_empty_search_returns_empty_and_skips_load(self):
        self.vector_store.search_vectors.return_value = []
        result = self.service.retrieve_semantic("q")
        self.assertEqual(result, [])
        self.messages.get_by_ids.assert_not_called()

    def test_semantic_empty_repository_result_handled_safely(self):
        # Vector store has ids, but PostgreSQL has none of them (stale index).
        mid = uuid.uuid4()
        self._configure_semantic([(str(mid), 0.9)], [])
        result = self.service.retrieve_semantic("q")
        self.assertEqual(list(result), [])

    def test_semantic_skips_ids_missing_from_postgres(self):
        present, missing = uuid.uuid4(), uuid.uuid4()
        ranked = [(str(present), 0.9), (str(missing), 0.8)]
        rows = [SimpleNamespace(id=present, content="P")]
        self._configure_semantic(ranked, rows)
        result = self.service.retrieve_semantic("q")
        self.assertEqual([r.id for r in result], [present])

    def test_semantic_no_duplicate_retrieval(self):
        mid = uuid.uuid4()
        self._configure_semantic([(str(mid), 0.9)], self._rows([mid]))
        self.service.retrieve_semantic("q")
        self.assertEqual(self.embeddings.generate_embedding.call_count, 1)
        self.assertEqual(self.vector_store.search_vectors.call_count, 1)
        self.assertEqual(self.messages.get_by_ids.call_count, 1)

    def test_semantic_returns_postgres_rows_not_scores_or_payloads(self):
        mid = uuid.uuid4()
        rows = self._rows([mid])
        self._configure_semantic([(str(mid), 0.9)], rows)
        result = self.service.retrieve_semantic("q")
        # The returned objects are the PostgreSQL rows, not (id, score) tuples.
        self.assertIs(result[0], rows[0])
        self.assertFalse(any(isinstance(r, tuple) for r in result))

    def test_semantic_embedding_failure_propagates(self):
        self.embeddings.generate_embedding.side_effect = RuntimeError("embed x")
        with self.assertRaises(RuntimeError):
            self.service.retrieve_semantic("q")
        self.vector_store.search_vectors.assert_not_called()

    def test_semantic_vector_store_failure_propagates(self):
        self.embeddings.generate_embedding.return_value = self.query_vector
        self.vector_store.search_vectors.side_effect = RuntimeError("qdrant x")
        with self.assertRaises(RuntimeError):
            self.service.retrieve_semantic("q")
        self.messages.get_by_ids.assert_not_called()

    def test_semantic_uses_default_limit(self):
        mid = uuid.uuid4()
        self._configure_semantic([(str(mid), 0.9)], self._rows([mid]))
        self.service.retrieve_semantic("q")
        # Default top-K is passed through to the vector store.
        self.assertEqual(
            self.vector_store.search_vectors.call_args.args[2], 10
        )

    def test_semantic_requires_injected_collaborators(self):
        # Without an embedding service wired (provider seam unfulfilled),
        # semantic retrieval is unavailable and fails clearly.
        service = MemoryRetrievalService(self.messages, None, None)
        with self.assertRaises(RuntimeError):
            service.retrieve_semantic("q")


if __name__ == "__main__":
    unittest.main()
