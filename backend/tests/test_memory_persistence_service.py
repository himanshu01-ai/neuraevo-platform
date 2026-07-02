"""Unit tests for the Memory Persistence Service (Sprint 8.1; 10.3 indexing).

Every dependency is mocked (session, message repository, embedding service, and
vector store), so no database, embedding API, or Qdrant is touched. The tests
verify that ``persist`` writes exactly the user then the assistant message under
the given conversation, commits atomically, propagates repository failures (with
rollback), and — as of Sprint 10.3 — after the commit generates one embedding
and upserts one vector, in that order, while never rolling back or losing the
persisted memory when embedding or indexing fails.

Runnable with stdlib unittest (no pytest dependency required):
    PYTHONPATH=. python -m unittest tests.test_memory_persistence_service
"""

import unittest
import uuid
from unittest.mock import MagicMock

from app.schemas.ai_response import AIResponse, AIResponseMetadata
from app.services.memory.memory_persistence_service import (
    MemoryPersistenceService,
)
from app.utils.constants import MessageRole

_LOGGER = "app.services.memory.memory_persistence_service"


class MemoryPersistenceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.owner = MagicMock(name="User")
        self.owner.id = uuid.uuid4()
        self.employee_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()
        self.memory_id = uuid.uuid4()
        self.user_message = "What's on my calendar today?"
        self.ai_response = AIResponse(
            content="You have a 3pm sync.",
            metadata=AIResponseMetadata(
                provider="test-provider",
                language="en",
                employee_id=self.employee_id,
                conversation_id=self.conversation_id,
                prompt_message_count=2,
            ),
        )

        self.session = MagicMock(name="Session")
        self.messages = MagicMock(name="MessageRepository")
        self.user_msg = MagicMock(name="user_msg")
        self.assistant_msg = MagicMock(name="assistant_msg")
        # The persisted assistant memory carries the PostgreSQL id/content used
        # for the post-commit vector index.
        self.assistant_msg.id = self.memory_id
        self.assistant_msg.content = self.ai_response.content
        self.messages.create_message.side_effect = [
            self.user_msg,
            self.assistant_msg,
        ]

        self.vector = [0.1, -0.2, 0.3]
        self.embeddings = MagicMock(name="EmbeddingService")
        self.embeddings.generate_embedding.return_value = self.vector
        self.vector_store = MagicMock(name="VectorStoreService")

        self.service = MemoryPersistenceService(
            self.session, self.messages, self.embeddings, self.vector_store
        )

    def _persist(self):
        return self.service.persist(
            self.owner,
            self.employee_id,
            self.conversation_id,
            self.user_message,
            self.ai_response,
        )

    def _create_calls(self):
        return self.messages.create_message.call_args_list

    # --- return value ----------------------------------------------------
    def test_returns_none(self):
        self.assertIsNone(self._persist())

    # --- writes ----------------------------------------------------------
    def test_exactly_two_messages_saved(self):
        self._persist()
        self.assertEqual(self.messages.create_message.call_count, 2)

    def test_user_message_saved_once(self):
        self._persist()
        user_calls = [
            c for c in self._create_calls() if c.args[1].role == MessageRole.USER
        ]
        self.assertEqual(len(user_calls), 1)

    def test_assistant_message_saved_once(self):
        self._persist()
        assistant_calls = [
            c
            for c in self._create_calls()
            if c.args[1].role == MessageRole.ASSISTANT
        ]
        self.assertEqual(len(assistant_calls), 1)

    def test_correct_conversation_id_passed(self):
        self._persist()
        for call in self._create_calls():
            self.assertEqual(call.args[0], self.conversation_id)

    def test_message_order_user_then_assistant(self):
        self._persist()
        roles = [c.args[1].role for c in self._create_calls()]
        self.assertEqual(roles, [MessageRole.USER, MessageRole.ASSISTANT])

    def test_user_content_stored_correctly(self):
        self._persist()
        self.assertEqual(self._create_calls()[0].args[1].content, self.user_message)

    def test_ai_response_content_stored_correctly(self):
        self._persist()
        self.assertEqual(
            self._create_calls()[1].args[1].content, self.ai_response.content
        )

    # --- transaction -----------------------------------------------------
    def test_commit_called_once_no_rollback(self):
        self._persist()
        self.session.commit.assert_called_once()
        self.session.rollback.assert_not_called()

    def test_repository_exception_propagates_and_rolls_back(self):
        self.messages.create_message.side_effect = RuntimeError("db down")
        with self.assertRaises(RuntimeError):
            self._persist()
        self.session.rollback.assert_called_once()
        self.session.commit.assert_not_called()

    # --- owner / employee provenance ------------------------------------
    def test_correct_owner_and_employee_id_used(self):
        with self.assertLogs(_LOGGER, level="INFO") as captured:
            self._persist()
        output = "\n".join(captured.output)
        self.assertIn(str(self.owner.id), output)
        self.assertIn(str(self.employee_id), output)
        self.assertIn(str(self.conversation_id), output)

    # --- statelessness / DI ---------------------------------------------
    def test_stateless_only_injected_collaborators(self):
        self.assertEqual(
            set(vars(self.service)),
            {"session", "messages", "embeddings", "vector_store"},
        )

    def test_constructor_uses_injected_dependencies(self):
        self.assertIs(self.service.session, self.session)
        self.assertIs(self.service.messages, self.messages)
        self.assertIs(self.service.embeddings, self.embeddings)
        self.assertIs(self.service.vector_store, self.vector_store)

    def test_di_provider_wires_repository_without_manual_instantiation(self):
        from app.core.dependencies import get_memory_persistence_service
        from app.repositories.message_repository import MessageRepository

        session = MagicMock(name="Session")
        embeddings = MagicMock(name="EmbeddingService")
        vector_store = MagicMock(name="VectorStoreService")
        service = get_memory_persistence_service(
            session, embeddings, vector_store
        )
        self.assertIsInstance(service, MemoryPersistenceService)
        self.assertIsInstance(service.messages, MessageRepository)
        self.assertIs(service.session, session)
        self.assertIs(service.embeddings, embeddings)
        self.assertIs(service.vector_store, vector_store)

    def test_indexing_embedding_service_none_until_provider_ready(self):
        # The composition-root assembler tolerates Sprint 10.1's unfulfilled
        # provider seam, so the runtime DI chain resolves (embeddings -> None).
        from app.core.dependencies import get_indexing_embedding_service

        self.assertIsNone(get_indexing_embedding_service())

    # =================================================================
    # Sprint 10.3 — post-commit vector indexing
    # =================================================================

    # --- happy path: embed once, upsert once ----------------------------
    def test_embedding_generated_once_with_assistant_content(self):
        self._persist()
        self.embeddings.generate_embedding.assert_called_once_with(
            self.ai_response.content
        )

    def test_vector_upserted_exactly_once(self):
        self._persist()
        self.assertEqual(self.vector_store.upsert_vector.call_count, 1)

    def test_no_duplicate_indexing(self):
        self._persist()
        self.assertEqual(self.embeddings.generate_embedding.call_count, 1)
        self.assertEqual(self.vector_store.upsert_vector.call_count, 1)

    def test_upsert_uses_memory_id_vector_and_collection(self):
        self._persist()
        kwargs = self.vector_store.upsert_vector.call_args.kwargs
        self.assertEqual(kwargs["collection_name"], "memories")
        self.assertEqual(kwargs["point_id"], str(self.memory_id))
        self.assertEqual(kwargs["vector"], self.vector)
        payload = kwargs["payload"]
        self.assertEqual(payload["memory_id"], str(self.memory_id))
        self.assertEqual(payload["user_id"], str(self.owner.id))
        self.assertEqual(payload["employee_id"], str(self.employee_id))
        self.assertEqual(payload["conversation_id"], str(self.conversation_id))
        self.assertEqual(payload["content"], self.ai_response.content)

    # --- execution order: DB first, then embed, then upsert --------------
    def test_execution_order_db_commit_then_embed_then_upsert(self):
        order = []

        def _create(conversation_id, data):
            order.append(f"create:{data.role.value}")
            return (
                self.user_msg
                if data.role == MessageRole.USER
                else self.assistant_msg
            )

        self.messages.create_message.side_effect = _create
        self.session.commit.side_effect = lambda: order.append("commit")
        self.embeddings.generate_embedding.side_effect = (
            lambda text: order.append("embed") or self.vector
        )
        self.vector_store.upsert_vector.side_effect = (
            lambda **kwargs: order.append("upsert")
        )

        self._persist()

        self.assertEqual(
            order,
            ["create:user", "create:assistant", "commit", "embed", "upsert"],
        )

    def test_database_persists_before_embedding(self):
        calls = []
        self.session.commit.side_effect = lambda: calls.append("commit")
        self.embeddings.generate_embedding.side_effect = (
            lambda text: calls.append("embed") or self.vector
        )
        self._persist()
        self.assertLess(calls.index("commit"), calls.index("embed"))

    # --- Case 1: DB write fails -> no embedding, no indexing -------------
    def test_db_create_failure_prevents_embedding_and_indexing(self):
        self.messages.create_message.side_effect = RuntimeError("db down")
        with self.assertRaises(RuntimeError):
            self._persist()
        self.session.rollback.assert_called_once()
        self.embeddings.generate_embedding.assert_not_called()
        self.vector_store.upsert_vector.assert_not_called()

    def test_db_commit_failure_prevents_embedding_and_indexing(self):
        self.session.commit.side_effect = RuntimeError("commit failed")
        with self.assertRaises(RuntimeError):
            self._persist()
        self.session.rollback.assert_called_once()
        self.embeddings.generate_embedding.assert_not_called()
        self.vector_store.upsert_vector.assert_not_called()

    # --- Case 2: embedding fails -> DB intact, no upsert ----------------
    def test_embedding_failure_leaves_db_intact_and_skips_upsert(self):
        self.embeddings.generate_embedding.side_effect = RuntimeError("embed x")
        # persist must NOT raise: a saved memory is never lost to indexing.
        self.assertIsNone(self._persist())
        self.session.commit.assert_called_once()
        self.session.rollback.assert_not_called()
        self.vector_store.upsert_vector.assert_not_called()

    # --- Case 3: vector upsert fails -> DB intact -----------------------
    def test_vector_upsert_failure_leaves_db_intact(self):
        self.vector_store.upsert_vector.side_effect = RuntimeError("qdrant x")
        self.assertIsNone(self._persist())
        self.session.commit.assert_called_once()
        self.session.rollback.assert_not_called()
        # Embedding still happened once; the failure was only at upsert.
        self.embeddings.generate_embedding.assert_called_once()

    # --- indexing disabled when no embedding provider is wired ----------
    def test_indexing_skipped_when_embeddings_none(self):
        service = MemoryPersistenceService(
            self.session, self.messages, None, self.vector_store
        )
        result = service.persist(
            self.owner,
            self.employee_id,
            self.conversation_id,
            self.user_message,
            self.ai_response,
        )
        self.assertIsNone(result)
        self.session.commit.assert_called_once()
        self.vector_store.upsert_vector.assert_not_called()


if __name__ == "__main__":
    unittest.main()
